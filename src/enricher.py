"""Data enrichment agent — fills missing fields via Claude web search."""

import json
import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch
from dotenv import load_dotenv

from typing import Callable, Optional
try:
    from .utils import normalize_phone, normalize_url
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.utils import normalize_phone, normalize_url

load_dotenv(override=True)


class DataEnricherAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0
        )
        self.search_tool = TavilySearch(max_results=3)
        self.prompt_template = self._load_prompt()

    def _load_prompt(self):
        prompt_path = Path(__file__).parent.parent / "prompts" / "enricher_prompt.md"
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read().replace("{", "{{").replace("}", "}}")

        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Company to enrich: {company_name}\n\nExisting data:\n{existing_data}\n\nSearch results:\n{search_results}")
        ])
    
    def search_company(self, company_name: str) -> str:
        """Search the web for company information."""
        try:
            results = self.search_tool.invoke(f"{company_name} company headquarters address industry")
            return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Search Failed: {str(e)}"
        
    def enrich_record(self, record: dict) -> dict:
        """Enrich a single customer record with web data."""
        company_name = record.get("company_name", "")

        # Step 1: Search the Web
        print(f"[Search] Searching for: {company_name}")
        search_results = self.search_company(company_name)

        # Step 2: Let LLM extract and structure the info
        chain = self.prompt_template | self.llm

        response = chain.invoke({
            "company_name": company_name,
            "existing_data": json.dumps(record, ensure_ascii=False),
            "search_results": search_results
        })

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            enriched_data = json.loads(content.strip())

            # Start with the original record as the base so all original fields
            # (company_name, address, contact_email, phone, etc.) are preserved.
            result = dict(record)

            # Handle legacy field names in case the LLM still uses old format
            legacy_map = {
                "verified_name": "company_name",
                "verified_address": "address",
                "industry_nace": "industry",
                "industry_description": "industry",
            }
            for old_key, new_key in legacy_map.items():
                if enriched_data.get(old_key) and not result.get(new_key):
                    result[new_key] = enriched_data.pop(old_key)

            # Core fields: only fill in if currently empty or MISSING
            core_fields = ["company_name", "address", "city", "postal_code",
                           "country", "industry", "contact_email", "phone", "website"]
            for field in core_fields:
                existing = result.get(field, "")
                if (not existing or existing == "MISSING") and enriched_data.get(field):
                    result[field] = enriched_data[field]

            # New enrichment-only fields: always add/update
            enrichment_fields = ["employees", "revenue_eur", "key_products",
                                  "data_sources", "enrichment_confidence"]
            for field in enrichment_fields:
                if field in enriched_data:
                    result[field] = enriched_data[field]

            # Normalize phone and website regardless of whether they came from
            # the original record or were just filled in by the enricher.
            if result.get("phone"):
                result["phone"] = normalize_phone(result["phone"])
            if result.get("website"):
                result["website"] = normalize_url(result["website"])

            return result
        except (json.JSONDecodeError, IndexError):
            # Return original record on failure so the pipeline can continue
            return dict(record)
        
    def enrich_batch(self, records: list[dict]) -> list[dict]:
        """Enrich a batch of records."""
        enriched = []
        for i, record in enumerate(records):
            print(f"Enriching {i+1}/{len(records)}: {record.get('company_name', 'unknown')}")
            result = self.enrich_record(record)
            enriched.append(result)
        return enriched
    

if __name__ == "__main__":
    agent = DataEnricherAgent()
    test = {
        "company_name": "Henkel AG & Co. KGaA",
        "address": "Henkelstrasse 67",
        "city": "Duesseldorf",
        "country": "DE"
    }
    result = agent.enrich_record(test)
    print(json.dumps(result, indent=2, ensure_ascii=False))

