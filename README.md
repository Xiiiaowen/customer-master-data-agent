# 🏢 Customer Master Data Agent

An AI-powered pipeline that **cleans, deduplicates, enriches, and validates** B2B customer records using **OpenAI GPT-4o-mini** and **Tavily web search**, with a **Streamlit** dashboard.

---

## Features

| Step | What it does |
|------|-------------|
| **🧹 Clean** | Normalises company names (English-first standard), phones (E.164), emails, URLs, addresses and country codes (ISO 3166-1 alpha-2) |
| **🔍 Deduplicate** | Fuzzy name matching + same-postal-code signal + LLM verification — catches duplicates even when names are in different languages (e.g. Chinese vs English for the same HQ) |
| **🌐 Enrich** | Fills missing fields (industry, website, employee count, revenue) via live Tavily web search |
| **✅ Validate** | Scores each record for completeness, flags format errors and missing required fields |

### Sample results on the built-in dataset

| Metric | Before | After |
|--------|--------|-------|
| Input records | 53 | — |
| Duplicates removed | — | 20 |
| Avg data completeness | ~41 % | ~82 % |
| Valid records | 0 % | ~89 % |

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

- OpenAI key: <https://platform.openai.com/api-keys>
- Tavily key: <https://app.tavily.com>

### 3. Run the Streamlit dashboard

```bash
streamlit run app.py
```

Open <http://localhost:8501> in your browser.

### 4. (Optional) Run from the command line

```bash
python src/agent.py
```

Reads `data/sample_customers.csv` and writes results to `output/`.

---

## Project Structure

```
customer-master-data-agent/
├── .env                        # API keys (not committed)
├── .streamlit/
│   └── config.toml             # Streamlit theme (blue palette)
├── requirements.txt
├── app.py                      # Streamlit dashboard
├── data/
│   └── sample_customers.csv    # Sample input (53 messy B2B records)
├── prompts/
│   ├── cleaner_prompt.md       # System prompt for the cleaning agent
│   └── enricher_prompt.md      # System prompt for the enrichment agent
├── src/
│   ├── agent.py                # Pipeline orchestrator
│   ├── cleaner.py              # Data cleaning (GPT-4o-mini)
│   ├── enricher.py             # Web-search enrichment (Tavily + GPT-4o-mini)
│   ├── validator.py            # Data quality validation & deduplication
│   └── utils.py                # Shared helpers (phone/URL normalizers, flags)
└── output/                     # Processed CSVs saved here (gitignored)
```

---

## Python API

```python
import pandas as pd
from src.agent import run_pipeline

df = pd.read_csv("data/sample_customers.csv")

results = run_pipeline(
    df,
    steps=["Clean", "Validate"],   # skip "Enrich" to save time/cost
    output_dir="output",
)

print(results["final_df"])
print(results["validation_report"])
```

`run_pipeline` returns:

| Key | Type | Description |
|-----|------|-------------|
| `cleaned_df` | `DataFrame \| None` | Records after cleaning & deduplication |
| `enriched_df` | `DataFrame \| None` | Records after web enrichment |
| `validation_report` | `dict \| None` | Quality scores and per-record issues |
| `final_df` | `DataFrame` | Final output (always present) |

---

## Design Decisions

- **Markdown prompts** — agent instructions live in `.md` files for easy iteration and version control, inspired by production agent systems.
- **Multi-agent pipeline** — each agent has a single responsibility (clean / enrich / validate) for modularity and testability.
- **Hybrid deduplication** — fast fuzzy name matching pre-filters candidates; LLM verifies; same postal-code + country acts as a language-agnostic fallback to catch records whose names differ only due to language (e.g. 上海浦东发展银行 ↔ Shanghai Pudong Development Bank).
- **English-first name standard** — the cleaning agent uses the official English name when one is widely established, so the same company is consistently identified across records from different source systems.
- **Phone/URL normalization in code** — E.164 phone formatting and `http → https` URL upgrades are enforced in Python after LLM output, so web-search results that return raw phone strings are always corrected.

---

## Cost Tips

- **Clean + Validate only** — fast and cheap, no web calls.
- **Enrich** makes one Tavily search per record; use the *Max records to enrich* slider in the dashboard sidebar to cap spend during testing.
- Full pipeline on 53 records costs roughly **$0.10–0.20** in API credits.
