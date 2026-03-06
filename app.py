"""Streamlit dashboard for the Customer Master Data Agent."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.agent import run_pipeline

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Customer Master Data Agent",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Page background ───────────────────────────── */
[data-testid="stAppViewContainer"] > .main {
    background: #f8fafc;
}

/* ── Hero banner ────────────────────────────────── */
.hero-banner {
    background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 58%, #0284c7 100%);
    border-radius: 16px;
    padding: 2rem 2.5rem 1.8rem;
    color: white;
    margin-bottom: 1.4rem;
}
.hero-banner h1 {
    font-size: 1.9rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0 0 0.25rem;
}
.hero-banner .subtitle {
    font-size: 0.95rem;
    opacity: 0.85;
    margin: 0 0 0.9rem;
}
.step-chip {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    border: 1px solid rgba(255,255,255,0.35);
    border-radius: 20px;
    padding: 3px 13px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 5px;
    color: white;
}

/* ── Section micro-label ────────────────────────── */
.sec-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #94a3b8;
    margin: 1.3rem 0 0.5rem;
    display: flex;
    align-items: center;
    gap: 8px;
}
.sec-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #e2e8f0;
}

/* ── Metric cards ────────────────────────────────── */
[data-testid="metric-container"] {
    background: white !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}

/* ── Sidebar dark theme ──────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #0f172a !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #94a3b8 !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] strong {
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] hr {
    border-color: #1e293b !important;
}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label {
    color: #cbd5e1 !important;
}

/* ── Pipeline log (terminal style) ──────────────── */
.pipeline-log {
    background: #0f172a;
    color: #7dd3fc;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 0.8rem;
    line-height: 1.75;
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid #1e293b;
    white-space: pre-wrap;
    margin: 0.4rem 0 0.8rem;
}

/* ── Quality score bar ───────────────────────────── */
.score-wrap { margin-bottom: 1.5rem; }
.score-lbl  { font-size: 0.78rem; color: #64748b; margin-bottom: 5px; }
.score-row  { display: flex; align-items: center; gap: 14px; }
.score-track {
    flex: 1;
    background: #e2e8f0;
    border-radius: 99px;
    height: 12px;
    overflow: hidden;
}
.score-fill {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, #1d4ed8, #38bdf8);
}
.score-num {
    font-size: 1.55rem;
    font-weight: 800;
    color: #1d4ed8;
    min-width: 56px;
    text-align: right;
}

/* ── Validation table ────────────────────────────── */
.vt-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
    margin-top: 0.5rem;
}
.vt-table th {
    background: #f8fafc;
    color: #64748b;
    font-size: 0.69rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    padding: 9px 14px;
    text-align: left;
    border-bottom: 2px solid #e2e8f0;
}
.vt-table td {
    padding: 8px 14px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
}
.vt-table tr:last-child td { border-bottom: none; }
.vt-table tr:hover td { background: #f8fafc; }

/* status pills */
.pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 0.72rem;
    font-weight: 700;
    line-height: 1.7;
}
.pill-valid   { background: #d1fae5; color: #065f46; }
.pill-warning { background: #fef3c7; color: #92400e; }
.pill-error   { background: #fee2e2; color: #991b1b; }

/* ── Tab labels ──────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] {
    font-weight: 600;
    font-size: 0.87rem;
}

/* ── Hide Streamlit chrome ───────────────────────── */
#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [("results", None), ("logs", [])]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.divider()

    st.markdown("**Pipeline Steps**")
    run_clean    = st.checkbox("🧹  Clean & Deduplicate", value=True)
    run_enrich   = st.checkbox("🌐  Enrich via web search", value=False)
    run_validate = st.checkbox("✅  Validate quality", value=True)

    if run_enrich:
        enrich_max = st.slider(
            "Max records to enrich",
            min_value=1, max_value=20, value=5,
            help="Web enrichment is slow — limit to control cost and time.",
        )
    else:
        enrich_max = 5

    st.divider()
    st.markdown(
        "<small>Powered by<br><strong>OpenAI GPT-4o-mini</strong> · "
        "<strong>Tavily Search</strong></small>",
        unsafe_allow_html=True,
    )

# ── Active steps ──────────────────────────────────────────────────────────────
steps = []
if run_clean:    steps.append("Clean")
if run_enrich:   steps.append("Enrich")
if run_validate: steps.append("Validate")

_step_icons = {"Clean": "🧹 Clean", "Enrich": "🌐 Enrich", "Validate": "✅ Validate"}
_chips = " ".join(f'<span class="step-chip">{_step_icons[s]}</span>' for s in steps)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero-banner">
  <h1>🏢 Customer Master Data Agent</h1>
  <p class="subtitle">
    AI-powered pipeline that cleans, deduplicates, enriches and validates B2B customer records
  </p>
  <div>
    {_chips or "<span style='opacity:0.6;font-size:0.85rem'>No steps selected</span>"}
  </div>
</div>
""", unsafe_allow_html=True)

# ── File upload ───────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload a customer CSV  _(leave empty to use the built-in sample)_",
    type=["csv"],
)

if uploaded:
    df_input = pd.read_csv(uploaded)
else:
    sample_path = Path(__file__).parent / "data" / "sample_customers.csv"
    if sample_path.exists():
        df_input = pd.read_csv(sample_path)
        st.info(f"📂 Using built-in sample: **{sample_path.name}** — {len(df_input)} records")
    else:
        st.warning("No file uploaded and no sample data found. Please upload a CSV.")
        st.stop()

with st.expander(
    f"📋 Preview input data — {len(df_input)} records · {len(df_input.columns)} columns",
    expanded=False,
):
    st.dataframe(df_input, use_container_width=True, height=250)

# ── Steps guard ───────────────────────────────────────────────────────────────
if not steps:
    st.warning("☝️ Select at least one pipeline step in the sidebar.")
    st.stop()

# ── Run button ────────────────────────────────────────────────────────────────
run_btn = st.button("▶  Run Pipeline", type="primary", use_container_width=True)

if run_btn:
    st.session_state.logs = []
    st.session_state.results = None
    log_placeholder = st.empty()

    def append_log(msg: str) -> None:
        st.session_state.logs.append(f"› {msg}")
        log_placeholder.markdown(
            '<div class="pipeline-log">' + "\n".join(st.session_state.logs) + "</div>",
            unsafe_allow_html=True,
        )

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
        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            st.stop()

    st.success("✅ Pipeline finished successfully!")

# ── Results ───────────────────────────────────────────────────────────────────
if st.session_state.results:
    results = st.session_state.results
    report  = results.get("validation_report") or {}

    st.markdown('<p class="sec-label">📊 Summary</p>', unsafe_allow_html=True)

    # KPI row
    removed = len(df_input) - len(results["final_df"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Input Records",   len(df_input))
    c2.metric("After Clean & Dedup", len(results["final_df"]),
              delta=f"−{removed} removed", delta_color="inverse")
    if report:
        c3.metric("Valid Records",  report.get("valid_count", "—"))
        c4.metric("Quality Score",  f'{report.get("overall_score", 0)}%')
    else:
        c3.metric("Valid Records",  "—")
        c4.metric("Quality Score",  "—")

    # Tabs
    tab_labels = []
    if results.get("cleaned_df")  is not None: tab_labels.append("🧹 Cleaned")
    if results.get("enriched_df") is not None: tab_labels.append("🌐 Enriched")
    if report:                                  tab_labels.append("✅ Validation")
    tab_labels.append("⬇ Final Output")

    tabs = st.tabs(tab_labels)
    t = 0

    # ── Cleaned tab ───────────────────────────────────────────────────────────
    if results.get("cleaned_df") is not None:
        with tabs[t]:
            df_c = results["cleaned_df"]
            st.caption(f"{len(df_c)} records · {len(df_c.columns)} columns")
            st.dataframe(df_c, use_container_width=True, height=400)
            st.download_button(
                "⬇ Download Cleaned CSV",
                df_c.to_csv(index=False).encode(),
                "cleaned_customers.csv", "text/csv",
            )
        t += 1

    # ── Enriched tab ──────────────────────────────────────────────────────────
    if results.get("enriched_df") is not None:
        with tabs[t]:
            df_e = results["enriched_df"]
            st.caption(f"{len(df_e)} records · {len(df_e.columns)} columns")
            st.dataframe(df_e, use_container_width=True, height=400)
            st.download_button(
                "⬇ Download Enriched CSV",
                df_e.to_csv(index=False).encode(),
                "enriched_customers.csv", "text/csv",
            )
        t += 1

    # ── Validation tab ────────────────────────────────────────────────────────
    if report:
        with tabs[t]:
            score = report.get("overall_score", 0)

            # Gradient quality bar
            st.markdown(f"""
            <div class="score-wrap">
              <div class="score-lbl">Overall Data Quality Score</div>
              <div class="score-row">
                <div class="score-track">
                  <div class="score-fill" style="width:{score}%"></div>
                </div>
                <div class="score-num">{score}%</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Mini KPIs
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Total",       report.get("total_records", 0))
            v2.metric("✅ Valid",    report.get("valid_count",   0))
            v3.metric("⚠️ Warnings", report.get("warning_count", 0))
            v4.metric("❌ Errors",   report.get("error_count",   0))

            # Per-record table
            if report.get("records"):
                st.markdown(
                    '<p class="sec-label" style="margin-top:1.4rem">Per-record detail</p>',
                    unsafe_allow_html=True,
                )
                _pill = {
                    "valid":   '<span class="pill pill-valid">Valid</span>',
                    "warning": '<span class="pill pill-warning">Warning</span>',
                    "error":   '<span class="pill pill-error">Error</span>',
                }
                rows_html = ""
                for rec in report["records"]:
                    status = rec.get("status", "unknown")
                    badge  = _pill.get(status, status)
                    name   = rec.get("company_name", "") or "—"
                    scr    = rec.get("score", 0)
                    issues = " · ".join(rec.get("issues", [])) or "—"
                    rows_html += f"""
                    <tr>
                      <td>{badge}</td>
                      <td><strong>{name}</strong></td>
                      <td>{scr}%</td>
                      <td style="color:#64748b;font-size:0.8rem">{issues}</td>
                    </tr>"""

                st.markdown(f"""
                <table class="vt-table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Company</th>
                      <th>Score</th>
                      <th>Issues / Warnings</th>
                    </tr>
                  </thead>
                  <tbody>{rows_html}</tbody>
                </table>
                """, unsafe_allow_html=True)

            with st.expander("📄 Raw validation JSON"):
                st.json(report)
        t += 1

    # ── Final output tab ──────────────────────────────────────────────────────
    with tabs[t]:
        final_df = results["final_df"]
        st.caption(f"{len(final_df)} records · {len(final_df.columns)} columns")
        st.dataframe(final_df, use_container_width=True, height=430)
        st.download_button(
            "⬇ Download Final Master Data CSV",
            final_df.to_csv(index=False).encode(),
            "final_customers.csv", "text/csv",
            type="primary",
            use_container_width=True,
        )
