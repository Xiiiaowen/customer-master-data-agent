"""Main agent orchestrator — runs the full clean → enrich → validate pipeline."""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional
try:
    from .cleaner import DataCleanerAgent
    from .enricher import DataEnricherAgent
    from .validator import DataValidatorAgent
except ImportError:
    # Allow running this file directly: python src/agent.py
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.cleaner import DataCleanerAgent
    from src.enricher import DataEnricherAgent
    from src.validator import DataValidatorAgent


def _to_record(item) -> Optional[dict]:
    """Normalise a cleaner output to a single dict.

    The LLM sometimes wraps its JSON in an array ([{...}] instead of {...}).
    If the item is already a dict, return it as-is.
    If it is a list, return the first dict element found inside it.
    Returns None for anything else (unparseable / empty).
    """
    if isinstance(item, dict):
        return item
    if isinstance(item, list):
        for elem in item:
            if isinstance(elem, dict):
                return elem
    return None


class CustomerMasterDataAgent:
    """
    Main orchestrator that runs the full pipeline:
    Raw Data → Clean → Deduplicate → Enrich → Validate → Output
    """

    def __init__(self):
        self.cleaner = DataCleanerAgent()
        self.enricher = DataEnricherAgent()
        self.validator = DataValidatorAgent()

    def run_pipeline(self, input_path: str, output_dir: str = "output") -> dict:
        """Run the full master data pipeline (CLI entry point)."""
        print("=" * 60)
        print("🚀 Customer Master Data Agent - Starting Pipeline")
        print("=" * 60)

        # Load data
        print("\n📂 Step 1: Loading data...")
        df = pd.read_csv(input_path)
        records = df.to_dict("records")
        print(f"   Loaded {len(records)} records")

        # Clean
        print("\n🧹 Step 2: Cleaning records...")
        cleaned = [r for r in (_to_record(x) for x in self.cleaner.clean_batch(records)) if r is not None]
        print(f"   Cleaned {len(cleaned)} records")

        # Deduplicate
        print("\n🔍 Step 3: Finding duplicates...")
        duplicates = self.validator.find_duplicates(cleaned)
        print(f"   Found {len(duplicates)} duplicate pairs")

        unique = self._remove_duplicates(cleaned, duplicates)
        print(f"   {len(unique)} unique records remaining")

        # Enrich
        print("\n🌐 Step 4: Enriching with web data...")
        enriched = self.enricher.enrich_batch(unique)
        print(f"   Enriched {len(enriched)} records")

        # Validate
        print("\n✅ Step 5: Validating final data...")
        validated = [self.validator.validate_record(r) for r in enriched]

        valid_count = sum(1 for v in validated if v["is_valid"])
        # Bug fix: guard against empty validated list
        avg_completeness = (
            sum(v["completeness"] for v in validated) / len(validated)
            if validated else 0.0
        )

        print(f"   Valid: {valid_count}/{len(validated)}")
        print(f"   Avg completeness: {avg_completeness:.0%}")

        # Save outputs
        print("\n💾 Step 6: Saving results...")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        output_file = output_path / f"master_data_{timestamp}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)

        csv_file = output_path / f"master_data_{timestamp}.csv"
        pd.DataFrame(enriched).to_csv(csv_file, index=False, encoding="utf-8")

        report = {
            "timestamp": timestamp,
            "input_records": len(records),
            "duplicates_found": len(duplicates),
            "unique_records": len(unique),
            "valid_records": valid_count,
            "avg_completeness": round(avg_completeness, 2),
            "duplicate_details": duplicates,
            "validation_issues": [v for v in validated if not v["is_valid"]]
        }

        report_file = output_path / f"report_{timestamp}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n   📊 Results saved to {output_path}/")
        print("=" * 60)
        print("✨ Pipeline complete!")
        print("=" * 60)

        return report

    def _remove_duplicates(self, records: list, duplicates: list) -> list:
        """Remove duplicate records, keeping the more complete one."""
        ids_to_remove = set()
        for dup in duplicates:
            r1 = dup["record_1"]
            r2 = dup["record_2"]
            c1 = self.validator._calc_completeness(r1)
            c2 = self.validator._calc_completeness(r2)
            remove = r2 if c1 >= c2 else r1
            ids_to_remove.add(id(remove))

        return [r for r in records if id(r) not in ids_to_remove]


def run_pipeline(
    df: pd.DataFrame,
    steps: List[str],
    enrich_max_records: int = 5,
    output_dir: str = "output",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Module-level entry point for app.py (Streamlit UI).

    Returns a dict with:
      - cleaned_df: pd.DataFrame or None
      - enriched_df: pd.DataFrame or None
      - validation_report: dict or None
      - final_df: pd.DataFrame  (always present)
    """
    log = progress_callback or (lambda _: None)

    records = df.to_dict("records")
    log(f"Loaded {len(records)} records.")

    agent = CustomerMasterDataAgent()

    cleaned_df = None
    enriched_df = None
    validation_report = None
    current = records

    # Step: Clean + deduplicate
    if "Clean" in steps:
        log("Cleaning records...")
        cleaned = [r for r in (_to_record(x) for x in agent.cleaner.clean_batch(current)) if r is not None]

        log("Detecting duplicates...")
        duplicates = agent.validator.find_duplicates(cleaned)
        log(f"Found {len(duplicates)} duplicate pair(s).")

        cleaned = agent._remove_duplicates(cleaned, duplicates)
        log(f"{len(cleaned)} unique records after deduplication.")

        cleaned_df = pd.DataFrame(cleaned)
        current = cleaned

    # Step: Enrich
    if "Enrich" in steps:
        to_enrich = current[:enrich_max_records]
        rest = current[enrich_max_records:]
        log(f"Enriching {len(to_enrich)} record(s)...")
        enriched = agent.enricher.enrich_batch(to_enrich)
        current = enriched + rest
        enriched_df = pd.DataFrame(current)
        log("Enrichment complete.")

    # Step: Validate
    if "Validate" in steps:
        log("Validating records...")
        validated = [agent.validator.validate_record(r) for r in current]

        valid_count = sum(1 for v in validated if v["is_valid"])
        warning_count = sum(1 for v in validated if v["warnings"])
        error_count = sum(1 for v in validated if not v["is_valid"])
        avg_completeness = (
            sum(v["completeness"] for v in validated) / len(validated)
            if validated else 0.0
        )

        records_detail = []
        for v in validated:
            rec = v["record"]
            if not v["is_valid"]:
                status = "error"
            elif v["warnings"]:
                status = "warning"
            else:
                status = "valid"
            records_detail.append({
                "status": status,
                "customer_id": rec.get("customer_id", ""),
                "company_name": rec.get("company_name", ""),
                "score": round(v["completeness"] * 100),
                "issues": v["issues"] + v["warnings"],
            })

        validation_report = {
            "total_records": len(validated),
            "valid_count": valid_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "overall_score": round(avg_completeness * 100),
            "records": records_detail,
        }
        log(f"Validation done: {valid_count}/{len(validated)} valid.")

    # Save final CSV
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    final_df = pd.DataFrame(current)
    final_df.to_csv(output_path / f"master_data_{timestamp}.csv", index=False, encoding="utf-8")
    log(f"Saved results to {output_dir}/")

    return {
        "cleaned_df": cleaned_df,
        "enriched_df": enriched_df,
        "validation_report": validation_report,
        "final_df": final_df,
    }


if __name__ == "__main__":
    agent = CustomerMasterDataAgent()
    default_input = Path(__file__).parent.parent / "data" / "sample_customers.csv"
    default_output = Path(__file__).parent.parent / "output"
    report = agent.run_pipeline(str(default_input), str(default_output))
    print(f"\nFinal report saved to: {default_output}")
    print(f"\nFinal report: {json.dumps(report, indent=2, ensure_ascii=False)}")