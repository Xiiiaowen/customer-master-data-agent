"""Streamlit dashboard for the Customer Master Data Agent."""

import io
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.agent import run_pipeline

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Customer Master Data Agent",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ───────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = None
if "logs" not in st.session_state:
    st.session_state.logs = []

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")

    st.subheader("Pipeline Steps")
    run_clean = st.checkbox("Clean data", value=True)
    run_enrich = st.checkbox("Enrich data (uses web search)", value=False)
    run_validate = st.checkbox("Validate data", value=True)

    if run_enrich:
        enrich_max = st.slider(
            "Max records to enrich",
            min_value=1,
            max_value=20,
            value=5,
            help="Web search enrichment is slow — limit to control cost and time.",
        )
    else:
        enrich_max = 5

    st.divider()
    st.caption("Powered by OpenAI GPT-4o-mini + Tavily Search")

# ── Main content ─────────────────────────────────────────────────────────────
st.title("🏢 Customer Master Data Agent")
st.markdown(
    "Upload a customer CSV, choose pipeline steps, and let Claude clean, "
    "enrich, and validate your data."
)

# ── File upload ──────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload customer CSV",
    type=["csv"],
    help="Uses sample_customers.csv from the data/ folder if no file is uploaded.",
)

if uploaded:
    df_input = pd.read_csv(uploaded)
else:
    sample_path = Path(__file__).parent / "data" / "sample_customers.csv"
    if sample_path.exists():
        df_input = pd.read_csv(sample_path)
        st.info(f"Using sample data: {sample_path.name} ({len(df_input)} records)")
    else:
        st.warning("No file uploaded and no sample data found. Please upload a CSV.")
        st.stop()

st.subheader("Input Data")
st.dataframe(df_input, use_container_width=True, height=300)
st.caption(f"{len(df_input)} records · {len(df_input.columns)} columns")

# ── Run pipeline ─────────────────────────────────────────────────────────────
steps = []
if run_clean:
    steps.append("Clean")
if run_enrich:
    steps.append("Enrich")
if run_validate:
    steps.append("Validate")

if not steps:
    st.warning("Select at least one pipeline step in the sidebar.")
    st.stop()

run_btn = st.button("▶  Run Pipeline", type="primary", use_container_width=True)

if run_btn:
    st.session_state.logs = []
    log_box = st.empty()

    def append_log(msg: str) -> None:
        st.session_state.logs.append(msg)
        log_box.code("\n".join(st.session_state.logs), language=None)

    with st.spinner("Running pipeline…"):
        try:
            results = run_pipeline(
                df_input,
                steps=steps,
                enrich_max_records=enrich_max,
                output_dir=str(Path(__file__).parent / "output"),
                progress_callback=append_log,
            )
            st.session_state.results = results
            st.success("Pipeline finished!")
        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            st.stop()

# ── Results ──────────────────────────────────────────────────────────────────
if st.session_state.results:
    results = st.session_state.results
    st.divider()
    st.subheader("Results")

    tab_labels = []
    if results.get("cleaned_df") is not None:
        tab_labels.append("Cleaned Data")
    if results.get("enriched_df") is not None:
        tab_labels.append("Enriched Data")
    if results.get("validation_report"):
        tab_labels.append("Validation Report")
    tab_labels.append("Final Output")

    tabs = st.tabs(tab_labels)
    tab_idx = 0

    # Cleaned
    if results.get("cleaned_df") is not None:
        with tabs[tab_idx]:
            st.dataframe(results["cleaned_df"], use_container_width=True, height=400)
            _csv = results["cleaned_df"].to_csv(index=False).encode()
            st.download_button("⬇ Download Cleaned CSV", _csv, "cleaned_customers.csv", "text/csv")
        tab_idx += 1

    # Enriched
    if results.get("enriched_df") is not None:
        with tabs[tab_idx]:
            st.dataframe(results["enriched_df"], use_container_width=True, height=400)
            _csv = results["enriched_df"].to_csv(index=False).encode()
            st.download_button("⬇ Download Enriched CSV", _csv, "enriched_customers.csv", "text/csv")
        tab_idx += 1

    # Validation report
    if results.get("validation_report"):
        with tabs[tab_idx]:
            report = results["validation_report"]

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Records", report.get("total_records", 0))
            col2.metric("Valid", report.get("valid_count", 0), delta=None)
            col3.metric("Warnings", report.get("warning_count", 0))
            col4.metric("Errors", report.get("error_count", 0))

            overall = report.get("overall_score", 0)
            st.progress(overall / 100, text=f"Overall Data Quality Score: {overall}/100")

            # Per-record table
            if "records" in report and report["records"]:
                records_data = []
                for rec in report["records"]:
                    status = rec.get("status", "unknown")
                    icon = {"valid": "✅", "warning": "⚠️", "error": "❌"}.get(status, "❓")
                    records_data.append(
                        {
                            "Status": f"{icon} {status.capitalize()}",
                            "Customer ID": rec.get("customer_id", ""),
                            "Company": rec.get("company_name", ""),
                            "Score": rec.get("score", 0),
                            "Issues": " | ".join(rec.get("issues", [])) or "None",
                        }
                    )
                st.dataframe(
                    pd.DataFrame(records_data),
                    use_container_width=True,
                    height=400,
                )

            # Raw JSON
            with st.expander("Raw validation JSON"):
                st.json(report)
        tab_idx += 1

    # Final output
    with tabs[tab_idx]:
        final_df = results["final_df"]
        st.dataframe(final_df, use_container_width=True, height=400)
        st.caption(f"{len(final_df)} records · {len(final_df.columns)} columns")
        _csv = final_df.to_csv(index=False).encode()
        st.download_button(
            "⬇ Download Final CSV",
            _csv,
            "final_customers.csv",
            "text/csv",
            type="primary",
        )
