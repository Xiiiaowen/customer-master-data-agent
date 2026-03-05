"""Shared utility functions for the customer master data agent."""

import json
import re
import logging
from pathlib import Path


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
