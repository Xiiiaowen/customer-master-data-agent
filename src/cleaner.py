"""Data cleaning agent — normalizes and standardizes customer records using Claude."""

import json
import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from typing import Callable, Optional, List, Dict

load_dotenv(override=True)

class DataCleanerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  # cheaper :)
            temperature=0
        )
        self.prompt_template = self._load_template()
        self.llm_calls = 0

    def _load_template(self):
        prompt_path = Path(__file__).parent.parent / "prompts" / "cleaner_prompt.md"

        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read().replace("{", "{{").replace("}", "}}")

        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Clean this customer record:\n{record}")
        ])

    def clean_record(self, record: dict) -> dict:
        """Clean a single customer record."""
        chain = self.prompt_template | self.llm

        response = chain.invoke({
            "record": json.dumps(record, ensure_ascii=False)
        })
        self.llm_calls += 1

        try:
            # Extract JSON from response
            content = response.content
            # Handle case where LLM wraps in markdown code block
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())
        except (json.JSONDecodeError, IndentationError):
            return {"error": "Failed to parse LLM response",
                    "raw_response": response.content,
                    "original": record}

    def clean_batch(self, records: List[Dict]) -> List[Dict]:
        """Clean a batch of customer records."""
        cleaned = []
        for i, record in enumerate(records):
            print(f"Cleaning record {i+1}/{len(records)}: {record.get('company_name', 'unknown')}")
            result = self.clean_record(record)
            cleaned.append(result)

        return cleaned


# Quick test
if __name__ == "__main__":
    agent = DataCleanerAgent()
    test = {
        "company name": "henkel ag & co kgaa",
        "address": "henkelstr 67",
        "city": "dusseldorf",
        "country": "germany",
        "industry": "",
        "contact_email": "",
        "phone": "+49 211 797 -0"
    }
    result = agent.clean_record(test)
    print(json.dumps(result, indent=2, ensure_ascii=False))
