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

Open <http://localhost:8501> in your browser, or try the [live demo](https://customer-master-data-agent-3nyfjemy6tnrpfhtqvnz7u.streamlit.app/).

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
│   ├── cache.py                # File-based enrichment cache
│   └── utils.py                # Shared helpers (phone/URL normalizers, flags)
├── cache/                      # Enrichment cache (auto-generated, gitignored)
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
| `phase` | `str` | `"done"` on completion; `"review_duplicates"` if the pipeline paused for user input |
| `cleaned_df` | `DataFrame \| None` | Records after cleaning & deduplication |
| `enriched_df` | `DataFrame \| None` | Records after web enrichment |
| `validation_report` | `dict \| None` | Quality scores and per-record issues |
| `final_df` | `DataFrame` | Final output (always present on `"done"`) |
| `original_df` | `DataFrame` | Raw input before any processing (for diff comparison) |
| `record_changes` | `list` | Per-record field-level diffs (before → after from cleaning) |
| `cost_summary` | `dict` | LLM call counts, web searches, cache hits, estimated USD cost |

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
- **Enrich** makes one Tavily search + one GPT call per record on the first run. Repeat runs reuse the cache and cost nothing for already-processed companies.
- Use the *Max records to enrich* slider in the dashboard sidebar to cap spend during testing.
- First full pipeline run on 53 records costs roughly **$0.10–0.20** in API credits. Subsequent runs on the same dataset are near-zero for enrichment.

---

## What Changed in V2

V1 was a working prototype — clean, enrich, validate, done. V2 adds a few practical improvements that make it more useful for repeated, real-world use.

### Enrichment cache

The biggest day-to-day change. Enrichment results are now saved to `cache/enrichment_cache.json` after the first run. On subsequent runs, any company that's already been enriched skips the Tavily search and GPT call entirely — so you only pay API costs for genuinely new records.

**Side effect to be aware of:** The cache never expires on its own. If a company moves headquarters, gets acquired, or changes industry, the cached data stays stale until you delete the file. For most personal use this is fine — company facts don't change often. But if you're using this after a major corporate event (merger, rebranding), wipe `cache/enrichment_cache.json` and re-run.

### Duplicate review UI

Instead of auto-deleting one record from each detected duplicate pair, the pipeline now pauses and shows you both records side-by-side so you can decide: keep record 1, keep record 2, or keep both (if the agent was wrong and they're actually different companies).

**Side effect:** If your dataset has many duplicates, this adds a manual step before the pipeline continues. It's intentional — automatic silent deletion was the bigger risk — but worth knowing if you're processing a large file and want it to run unattended.

### Multi-format file upload

The upload now accepts CSV, Excel (`.xlsx` / `.xls`), and JSON in addition to CSV. Column names are also auto-mapped, so common variants like `email`, `CompanyName`, or `telephone` are silently renamed to what the pipeline expects.

**Side effect:** The auto-mapping is best-effort. If your column names are ambiguous or unusual, it may map the wrong column. Check the "Auto-mapped columns" info banner after uploading to confirm the mapping looks right before running.

### What-changed diff view

After cleaning, the Cleaned tab now shows a before/after diff for every field the cleaner modified. This makes it easy to catch cases where the LLM "corrected" something it shouldn't have.

**Side effect:** The diff compares records by position (first record in → first record out), so if the cleaner fails to parse a record and returns nothing, the diff alignment for subsequent records shifts. In practice this is rare, but a garbled diff on a specific record is usually a sign the cleaner had trouble with it.

### Cost tracking

Each run now shows LLM call counts, web searches, cache hits, and an estimated USD cost at the bottom of the results page. The estimate is based on average token counts per call type — actual cost may be slightly higher or lower depending on how verbose the LLM is for a given record.

### Removed: cleaner confidence score

V1 asked the LLM to output a `confidence` field alongside each cleaned record. In practice it almost always returned 0.90–0.95 regardless of how uncertain the cleaning actually was, so it wasn't meaningful. The field has been removed from the cleaner output and the validator no longer checks it. The enricher's `enrichment_confidence` field is kept — there the LLM is judging the quality of its web search results, which is a more grounded assessment.

---

## What It Does Well

For a prototype, it handles a surprising amount of real-world mess:

- **The pipeline structure is solid.** Clean → deduplicate → enrich → validate is the right order, and each step is isolated enough that you can run them independently or skip ones you don't need.
- **It deals with genuinely hard input.** The sample dataset has Chinese company names, mixed-language duplicates (上海浦东发展银行 vs Shanghai Pudong Development Bank), inconsistent formatting, test rows, whitespace noise, and records with partial overlap across multiple sources. Most rule-based cleaners would fail on this.
- **Deduplication goes beyond simple string matching.** Using both fuzzy name similarity *and* same-postal-code-plus-country as signals catches duplicates that share an address but have completely different-looking names — which is common when a company has both a local and an English trade name.
- **LLM decisions are auditable in concept.** The LLM confirms or rejects duplicate candidates with a reason, which means the logic is explainable rather than a black box similarity score.
- **Prompt files are separate from code.** Keeping agent instructions in `.md` files makes it easy to tune behavior without touching Python, which is how you'd actually iterate on this in practice.
- **The UI is genuinely usable.** The Streamlit dashboard lets non-technical users upload a file, pick steps, see what changed at each stage, and download results — that's more than most data quality proofs-of-concept bother with.

---

## What's Missing for Production

This project works well as a proof-of-concept, but there's a fair amount of ground to cover before it's ready for real enterprise use. Here's an honest rundown:

### Scalability

The duplicate detection loops over every pair of records — fine for a demo dataset of 50, but it blows up at 50k records. Real MDM systems narrow candidates first (blocking by postal code, first letter of name, Soundex) before doing any fuzzy matching, which keeps things manageable.

Similarly, enrichment runs one record at a time. 100 records at ~4 seconds each means a 7-minute wait. Async parallel calls with a concurrency limit would cut that down significantly.

### No incremental processing

Every run re-processes the full dataset from scratch for cleaning and validation. The enrichment cache (added in V2) helps — already-enriched companies are skipped — but cleaning and validation still run on every record every time. A proper solution would track which records are new or changed and skip unchanged ones entirely.

### The duplicate merge is too simple

V2 added a human review step where you choose which record to keep per duplicate pair. That's better than the V1 auto-delete, but it's still not a true golden record merge. Ideally you'd take the best field from each source (email from CRM, address from ERP, phone from a third source) rather than picking one record wholesale and discarding the other entirely.

### No audit trail

There's no record of what changed and why. If someone asks "why does this company's country show DE when we originally had Germany?", there's no answer. Enterprise data teams need full lineage — who changed what, when, and with what confidence — especially in regulated industries.

### No human review step (partially addressed in V2)

Duplicate merges now require manual review in the UI before the pipeline continues. But other LLM decisions — field cleaning, enrichment values — are still applied automatically. Production MDM would route any low-confidence change to a stewardship queue, not just duplicates.

### No persistence layer

Results go to timestamped CSV files with no cleanup policy. There's no database, so you can't query records by quality score, track versions, or expose a clean API to downstream systems like a CRM or ERP.

### PII and access control

Customer emails, phones, and registration IDs are personal data under GDPR and similar regulations. There's no field-level encryption, no data masking, and no access controls on who can see what. The Streamlit app also has zero authentication — anyone who can reach port 8501 can upload files and burn through your API keys.

### Secrets management

The `.env` file sitting in the project directory is fine locally but is one accidental commit away from leaking credentials. In production, API keys belong in a secret manager (AWS Secrets Manager, HashiCorp Vault, etc.) not in a file on disk.

### No monitoring

`print()` is the only logging. You have no visibility into pipeline run history, cost per run, how enrichment confidence is trending, or alerts when the quality score drops. Structured logging and a few key metrics would go a long way.

---

**Priority order if this were heading to production:**

1. Database + incremental processing (biggest architectural gap)
2. Blocking strategy for deduplication (won't scale otherwise)
3. Retry logic and checkpointing (resilience for long runs)
4. Human stewardship queue (for borderline LLM decisions)
5. Auth and proper secrets management (before any real users touch it)
6. Audit trail (required for regulated industries)
