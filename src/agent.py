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
    from .utils import DUMMY_FLAGS
except ImportError:
    # Allow running this file directly: python src/agent.py
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.cleaner import DataCleanerAgent
    from src.enricher import DataEnricherAgent
    from src.validator import DataValidatorAgent
    from src.utils import DUMMY_FLAGS


def _is_test_record(record: dict) -> bool:
    """Return True if the record should be excluded from the pipeline."""
    name = record.get("company_name", "").strip()
    if not name or name.upper() == "MISSING":
        return True
    return any(flag in name.lower() for flag in DUMMY_FLAGS)


def _to_record(item) -> Optional[dict]:
    """Normalise a cleaner output to a single dict."""
    if isinstance(item, dict):
        return item
    if isinstance(item, list):
        for elem in item:
            if isinstance(elem, dict):
                return elem
    return None


def _compute_changes(original: list, cleaned: list) -> list:
    """Compare original and cleaned records field-by-field and return a diff list."""
    skip_fields = {"confidence", "data_quality_notes", "error", "raw_response", "original"}
    changes = []
    for orig, clean in zip(original, cleaned):
        if not isinstance(clean, dict):
            continue
        diff = {}
        all_keys = set(orig.keys()) | set(clean.keys())
        for key in all_keys:
            if key in skip_fields:
                continue
            before = str(orig.get(key, "")).strip()
            after = str(clean.get(key, "")).strip()
            if before != after:
                diff[key] = {"before": before or "(empty)", "after": after or "(empty)"}
        changes.append({
            "company_name": clean.get("company_name", orig.get("company_name", "unknown")),
            "changes": diff,
        })
    return changes


def _apply_duplicate_choices(cleaned: list, duplicates: list, choices: dict) -> list:
    """Apply user's keep/discard choices to a list of duplicate pairs."""
    indices_to_remove = set()
    for idx_str, choice in choices.items():
        idx = int(idx_str)
        if idx >= len(duplicates):
            continue
        dup = duplicates[idx]
        if choice == "keep_1":
            target = dup["record_2"]
        elif choice == "keep_2":
            target = dup["record_1"]
        else:  # "different" → keep both
            continue
        for i, r in enumerate(cleaned):
            if r == target:
                indices_to_remove.add(i)
                break
    return [r for i, r in enumerate(cleaned) if i not in indices_to_remove]


def _estimate_costs(cleaner, enricher, validator) -> dict:
    """Estimate API cost based on call counts and average token usage."""
    # GPT-4o-mini pricing: $0.150 / 1M input tokens, $0.600 / 1M output tokens
    PRICE_IN = 0.150 / 1_000_000
    PRICE_OUT = 0.600 / 1_000_000

    clean_cost  = cleaner.llm_calls  * (600  * PRICE_IN + 250 * PRICE_OUT)
    enrich_cost = enricher.llm_calls * (1500 * PRICE_IN + 500 * PRICE_OUT)
    valid_cost  = validator.llm_calls * (800  * PRICE_IN + 100 * PRICE_OUT)

    return {
        "cleaner_llm_calls":    cleaner.llm_calls,
        "enricher_llm_calls":   enricher.llm_calls,
        "enricher_search_calls": enricher.search_calls,
        "enricher_cache_hits":  enricher.cache_hits,
        "validator_llm_calls":  validator.llm_calls,
        "estimated_usd":        round(clean_cost + enrich_cost + valid_cost, 4),
        "note": "Rough estimate based on average token counts per call type.",
    }


class CustomerMasterDataAgent:
    """Orchestrator for the CLI entry point."""

    def __init__(self):
        self.cleaner = DataCleanerAgent()
        self.enricher = DataEnricherAgent()
        self.validator = DataValidatorAgent()

    def run_pipeline(self, input_path: str, output_dir: str = "output") -> dict:
        """Run the full master data pipeline (CLI entry point)."""
        print("=" * 60)
        print("🚀 Customer Master Data Agent - Starting Pipeline")
        print("=" * 60)

        print("\n📂 Step 1: Loading data...")
        df = pd.read_csv(input_path)
        records = df.to_dict("records")
        print(f"   Loaded {len(records)} records")

        print("\n🧹 Step 2: Cleaning records...")
        cleaned = [r for r in (_to_record(x) for x in self.cleaner.clean_batch(records)) if r is not None]
        print(f"   Cleaned {len(cleaned)} records")

        print("\n🔍 Step 3: Finding duplicates...")
        duplicates = self.validator.find_duplicates(cleaned)
        print(f"   Found {len(duplicates)} duplicate pairs")

        unique = _apply_duplicate_choices(cleaned, duplicates, {
            str(i): "keep_1" for i in range(len(duplicates))
        })
        unique = [r for r in unique if not _is_test_record(r)]
        print(f"   {len(unique)} records remaining after dedup")

        print("\n🌐 Step 4: Enriching with web data...")
        enriched = self.enricher.enrich_batch(unique)

        print("\n✅ Step 5: Validating final data...")
        validated = [self.validator.validate_record(r) for r in enriched]
        valid_count = sum(1 for v in validated if v["is_valid"])
        avg_completeness = (
            sum(v["completeness"] for v in validated) / len(validated)
            if validated else 0.0
        )

        print(f"   Valid: {valid_count}/{len(validated)}")
        print(f"   Avg completeness: {avg_completeness:.0%}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        with open(output_path / f"master_data_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)
        pd.DataFrame(enriched).to_csv(output_path / f"master_data_{timestamp}.csv", index=False, encoding="utf-8")

        report = {
            "timestamp": timestamp,
            "input_records": len(records),
            "duplicates_found": len(duplicates),
            "unique_records": len(unique),
            "valid_records": valid_count,
            "avg_completeness": round(avg_completeness, 2),
            "cost": _estimate_costs(self.cleaner, self.enricher, self.validator),
        }
        with open(output_path / f"report_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n   📊 Results saved to {output_path}/")
        print("=" * 60)
        print("✨ Pipeline complete!")
        print("=" * 60)
        return report


def run_pipeline(
    df: pd.DataFrame,
    steps: List[str],
    enrich_max_records: int = 5,
    output_dir: str = "output",
    progress_callback: Optional[Callable[[str], None]] = None,
    # Duplicate review params — set by app.py on the second call after user review
    duplicate_choices: Optional[dict] = None,
    _resume_records: Optional[list] = None,
    _all_duplicates: Optional[list] = None,
) -> dict:
    """
    Module-level entry point for app.py (Streamlit UI).

    Normal call:   run_pipeline(df, steps, ...)
    Resume call:   run_pipeline(df, steps, duplicate_choices={...},
                                _resume_records=[...], _all_duplicates=[...])

    Returns a dict with:
      phase              "review_duplicates" (paused) or "done"
      cleaned_df         DataFrame after cleaning (or None)
      enriched_df        DataFrame after enrichment (or None)
      validation_report  dict (or None)
      final_df           DataFrame (always present on "done")
      original_df        DataFrame of raw input (for diff view)
      record_changes     list of per-record field diffs
      proposed_duplicates list of pairs needing review (phase=="review_duplicates")
      cleaned_records    pre-dedup records for resume (phase=="review_duplicates")
      cost_summary       dict with call counts and estimated USD
    """
    log = progress_callback or (lambda _: None)

    records = df.to_dict("records")
    original_df = pd.DataFrame(records)

    agent = CustomerMasterDataAgent()

    cleaned_df = None
    enriched_df = None
    validation_report = None
    record_changes = []
    current = records

    # ── Clean + deduplicate ──────────────────────────────────────────────────
    if "Clean" in steps:
        if _resume_records is not None:
            # Resuming after user reviewed duplicates
            log("Applying your duplicate review choices...")
            cleaned = list(_resume_records)
            if _all_duplicates and duplicate_choices is not None:
                cleaned = _apply_duplicate_choices(cleaned, _all_duplicates, duplicate_choices)
                kept = sum(1 for v in duplicate_choices.values() if v != "different")
                log(f"Resolved {len(_all_duplicates)} pair(s): removed {kept} record(s).")
        else:
            # Fresh run — clean and detect duplicates
            log("Cleaning records...")
            cleaned_raw = agent.cleaner.clean_batch(current)
            cleaned = [r for r in (_to_record(x) for x in cleaned_raw) if r is not None]

            record_changes = _compute_changes(records, cleaned)

            log("Detecting duplicates...")
            duplicates = agent.validator.find_duplicates(cleaned)
            log(f"Found {len(duplicates)} duplicate pair(s).")

            if duplicates and duplicate_choices is None:
                # Pause pipeline — hand control back to the UI for user review
                log("Waiting for your input on duplicate pairs...")
                return {
                    "phase": "review_duplicates",
                    "proposed_duplicates": duplicates,
                    "cleaned_records": cleaned,
                    "original_df": original_df,
                    "record_changes": record_changes,
                }

            if duplicate_choices is not None:
                cleaned = _apply_duplicate_choices(cleaned, duplicates, duplicate_choices)
            log(f"{len(cleaned)} unique records after deduplication.")

        # Remove test/dummy records
        before = len(cleaned)
        cleaned = [r for r in cleaned if not _is_test_record(r)]
        if len(cleaned) < before:
            log(f"Removed {before - len(cleaned)} test/dummy record(s).")

        cleaned_df = pd.DataFrame(cleaned)
        current = cleaned

    # ── Enrich ───────────────────────────────────────────────────────────────
    if "Enrich" in steps:
        to_enrich = current[:enrich_max_records]
        rest = current[enrich_max_records:]
        log(f"Enriching {len(to_enrich)} record(s)...")
        enriched = agent.enricher.enrich_batch(to_enrich)
        current = enriched + rest
        enriched_df = pd.DataFrame(current)
        hits = agent.enricher.cache_hits
        if hits:
            log(f"Enrichment done — {hits} record(s) served from cache, {len(to_enrich) - hits} fetched from web.")
        else:
            log("Enrichment complete.")

    # ── Validate ─────────────────────────────────────────────────────────────
    if "Validate" in steps:
        log("Validating records...")
        validated = [agent.validator.validate_record(r) for r in current]

        valid_count   = sum(1 for v in validated if v["is_valid"])
        warning_count = sum(1 for v in validated if v["warnings"])
        error_count   = sum(1 for v in validated if not v["is_valid"])
        avg_completeness = (
            sum(v["completeness"] for v in validated) / len(validated)
            if validated else 0.0
        )

        records_detail = []
        for v in validated:
            rec = v["record"]
            status = "error" if not v["is_valid"] else ("warning" if v["warnings"] else "valid")
            records_detail.append({
                "status": status,
                "customer_id":  rec.get("customer_id", ""),
                "company_name": rec.get("company_name", ""),
                "score":  round(v["completeness"] * 100),
                "issues": v["issues"] + v["warnings"],
            })

        validation_report = {
            "total_records":   len(validated),
            "valid_count":     valid_count,
            "warning_count":   warning_count,
            "error_count":     error_count,
            "overall_score":   round(avg_completeness * 100),
            "records":         records_detail,
        }
        log(f"Validation done: {valid_count}/{len(validated)} valid.")

    # ── Save final CSV ────────────────────────────────────────────────────────
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    final_df = pd.DataFrame(current)
    final_df.to_csv(output_path / f"master_data_{timestamp}.csv", index=False, encoding="utf-8")
    log(f"Saved results to {output_dir}/")

    return {
        "phase": "done",
        "cleaned_df":        cleaned_df,
        "enriched_df":       enriched_df,
        "validation_report": validation_report,
        "final_df":          final_df,
        "original_df":       original_df,
        "record_changes":    record_changes,
        "cost_summary":      _estimate_costs(agent.cleaner, agent.enricher, agent.validator),
    }


if __name__ == "__main__":
    agent = CustomerMasterDataAgent()
    default_input  = Path(__file__).parent.parent / "data" / "sample_customers.csv"
    default_output = Path(__file__).parent.parent / "output"
    report = agent.run_pipeline(str(default_input), str(default_output))
    print(f"\nFinal report: {json.dumps(report, indent=2, ensure_ascii=False)}")
