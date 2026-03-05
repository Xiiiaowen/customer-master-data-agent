"""Data validation agent — detects duplicate records and validates completeness and format."""

import json
from difflib import SequenceMatcher
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv(override=True)

class DataValidatorAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini", 
            temperature=0)

    def find_duplicates(self, records: list[dict]) -> list[dict]:
        """Find potential duplicate records using fuzzy matching + LLM verification."""
        duplicates = []
        
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                name_i = records[i].get("company_name", "").lower().strip()
                name_j = records[j].get("company_name", "").lower().strip()
                
                # Quick fuzzy match first (cheap, no API call)
                similarity = SequenceMatcher(None, name_i, name_j).ratio()
                
                if similarity > 0.5:  # Potential match
                    # Use LLM to verify (more expensive but accurate)
                    is_duplicate = self._llm_verify_duplicate(records[i], records[j])
                    
                    if is_duplicate:
                        duplicates.append({
                            "record_1": records[i],
                            "record_2": records[j],
                            "similarity_score": round(similarity, 3),
                            "llm_confirmed": True
                        })
        
        return duplicates

    def _llm_verify_duplicate(self, record1: dict, record2: dict) -> bool:
        """Use LLM to verify if two records are duplicates."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data quality expert. Determine if these two
            customer records refer to the SAME company. Consider name variations,
            abbreviations, translations, and address similarities.

            Respond with ONLY a JSON object:
            {{"is_duplicate": true/false, "reason": "brief explanation"}}"""),
            ("user", "Record 1: {record1}\n\nRecord 2: {record2}")
        ])

        chain = prompt | self.llm
        response = chain.invoke({
            "record1": json.dumps(record1, ensure_ascii=False),
            "record2": json.dumps(record2, ensure_ascii=False)
        })
        
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content.strip())
            return result.get("is_duplicate", False)
        except:
            return False

    def validate_record(self, record: dict) -> dict:
        """Validate a single record for completeness and correctness."""
        issues = []
        warnings = []

        # Check required fields
        required = ["company_name", "address", "city", "country"]
        for field in required:
            if not record.get(field) or record.get(field) == "MISSING":
                issues.append(f"Missing required field: {field}")

        # Check country code format (must be 2-letter ISO)
        country = record.get("country", "")
        if country and len(country) != 2:
            issues.append(f"Invalid country code: '{country}' (should be 2-letter ISO, e.g. DE, US)")

        # Check email format (must have @ and domain with .)
        email = record.get("contact_email", "")
        if email and email != "MISSING":
            if "@" not in email:
                issues.append(f"Invalid email format: '{email}' (missing @)")
            elif "." not in email.split("@")[1]:
                issues.append(f"Invalid email format: '{email}' (missing domain extension)")

        # Check phone E.164 format (must start with +)
        phone = record.get("phone", "")
        if phone and phone != "MISSING" and not phone.startswith("+"):
            issues.append(f"Invalid phone format: '{phone}' (should be E.164, e.g. +4921179700)")

        # Check at least one contact method exists
        email_missing = not email or email == "MISSING"
        phone_missing = not phone or phone == "MISSING"
        if email_missing and phone_missing:
            issues.append("No contact method available (both email and phone are missing)")

        # Warn if cleaner confidence score is low
        confidence = record.get("confidence", 1.0)
        if isinstance(confidence, (int, float)) and confidence < 0.6:
            warnings.append(f"Low cleaner confidence: {confidence} (data may be unreliable)")

        # Warn if company name looks like test or dummy data
        company_name = record.get("company_name", "")
        dummy_flags = ["test", "n/a", "unknown", "dummy", "example"]
        if any(flag in company_name.lower() for flag in dummy_flags):
            warnings.append(f"Possible test/dummy record: '{company_name}'")

        return {
            "record": record,
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "completeness": self._calc_completeness(record)
        }

    def _calc_completeness(self, record: dict) -> float:
        """Calculate data completeness score."""
        fields = ["company_name", "address", "city", "postal_code",
                  "country", "industry", "contact_email", "phone", "website"]
        filled = sum(1 for f in fields 
                     if record.get(f) and record.get(f) != "MISSING")
        return round(filled / len(fields), 2)


if __name__ == "__main__":
    validator = DataValidatorAgent()
    
    # Test duplicate detection
    records = [
        {"company_name": "Henkel AG & Co. KGaA", "city": "Düsseldorf", "country": "DE"},
        {"company_name": "HENKEL AG", "city": "Dusseldorf", "country": "germany"},
        {"company_name": "BASF SE", "city": "Ludwigshafen", "country": "DE"}
    ]
    
    dupes = validator.find_duplicates(records)
    print(f"Found {len(dupes)} duplicate pairs:")
    for d in dupes:
        print(f"  - {d['record_1']['company_name']} ↔ {d['record_2']['company_name']} "
              f"(similarity: {d['similarity_score']})")