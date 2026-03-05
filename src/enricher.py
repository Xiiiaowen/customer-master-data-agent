"""Data enrichment agent — fills missing fields via Claude web search."""

import json
import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch
from dotenv import load_dotenv

from typing import Callable, Optional

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

            enriched = json.loads(content.strip())
            enriched["original_record"] = record
            return enriched
        except (json.JSONDecodeError, IndexError):
            return {
                "error": "Failed to parse enrichment response",
                "original record": record
            }
        
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

