# Customer Master Data Agent

An AI-powered pipeline that **cleans, deduplicates, enriches, and validates** B2B customer records using **OpenAI GPT-4o-mini** and **Tavily web search**, with a **Streamlit** dashboard.

## Features

| Step | What it does |
|------|-------------|
| **Clean** | Normalises company names, phones (E.164), emails, URLs, addresses and country codes (ISO 3166-1 alpha-2) |
| **Deduplicate** | Fuzzy name matching + LLM verification to find and remove duplicate records |
| **Enrich** | Fills missing fields (industry, website, employee count, revenue) via live Tavily web search |
| **Validate** | Scores each record for completeness, flags format errors and missing required fields |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

Copy `.env.example` to `.env` (or edit `.env` directly) and set:

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

## Project Structure

```
customer-master-data-agent/
├── .env                      # API keys (not committed)
├── requirements.txt
├── app.py                    # Streamlit dashboard
├── data/
│   └── sample_customers.csv  # Sample input data
├── prompts/
│   ├── cleaner_prompt.md     # System prompt for the cleaning agent
│   └── enricher_prompt.md    # System prompt for the enrichment agent
├── src/
│   ├── agent.py              # Pipeline orchestrator
│   ├── cleaner.py            # Data cleaning (GPT-4o-mini)
│   ├── enricher.py           # Web-search enrichment (Tavily + GPT-4o-mini)
│   ├── validator.py          # Data quality validation
│   └── utils.py              # Shared helpers
└── output/                   # Processed CSVs saved here (gitignored)
```

## Python API

```python
import pandas as pd
from src.agent import run_pipeline

df = pd.read_csv("data/sample_customers.csv")

results = run_pipeline(
    df,
    steps=["Clean", "Validate"],   # skip "Enrich" for speed/cost
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

## Cost Tips

- **Clean + Validate only** — fast and cheap, no web calls.
- **Enrich** makes one Tavily search per record; use the *Max records* slider in the dashboard sidebar to cap spend during testing.
