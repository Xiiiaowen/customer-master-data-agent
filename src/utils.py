"""Shared utility functions for the customer master data agent."""

import json
import re
import logging
from pathlib import Path

# Flags used to identify test / dummy records (shared by validator and agent)
DUMMY_FLAGS = ["test", "n/a", "unknown", "dummy", "example"]


def normalize_phone(phone: str) -> str:
    """Normalize a phone number to E.164 format (+[country code][digits]).

    Already-valid E.164 strings (start with + and contain only digits) are
    returned unchanged.  Otherwise all non-digit characters are stripped and a
    '+' prefix is added.  Strings that are empty, 'MISSING', or too short to be
    a real phone number are returned as-is.
    """
    if not phone or phone == "MISSING":
        return phone
    # Already clean E.164
    if re.match(r'^\+\d{7,15}$', phone.strip()):
        return phone.strip()
    # Strip everything except digits
    digits = re.sub(r'[^\d]', '', phone)
    if len(digits) < 7:
        return phone  # Too short — can't reliably normalize; preserve original
    return f"+{digits}"


def normalize_url(url: str) -> str:
    """Upgrade http:// to https:// and strip trailing slashes."""
    if not url or url == "MISSING":
        return url
    url = url.strip().rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url


def load_prompt(name: str) -> str:
    """Load a prompt markdown file by agent name."""
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{name}_prompt.md"
    return prompt_path.read_text(encoding="utf-8")


def extract_json(text: str):
    """
    Extract a JSON array or object from text that may contain markdown or prose.
    Returns the parsed Python object, or None if extraction fails.
    """
    # Try markdown code block first
    match = re.search(r"```(?:json)?\s*([\[{][\s\S]*?[\]}])\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a JSON array
    match = re.search(r"(\[[\s\S]*\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a JSON object
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def get_text_block(message) -> str:
    """
    Extract the last text block from an Anthropic message.
    Skips thinking blocks, returning only the final text response.
    """
    text_blocks = [
        b for b in message.content
        if hasattr(b, "type") and b.type == "text"
    ]
    return text_blocks[-1].text if text_blocks else ""


def setup_logging(name: str) -> logging.Logger:
    """Configure and return a module-level logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    return logging.getLogger(name)
