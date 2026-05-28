"""
Biomarker Concordance Pipeline — Streamlit Quality Dashboard

Panels:
  1. Run status table
  2. Concordance trend (SNV and INDEL F1/precision/recall)
  3. VAF reproducibility (ICC, CV, Bland-Altman summary)
  4. Active quality alerts
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Biomarker Concordance Dashboard",
    page_icon="🧬",
    layout="wide",
)

st.title("🧬 Biomarker Concordance Pipeline")
st.caption("Germline variant calling quality monitoring · GIAB HG001 v4.2.1 truth set")


def api_get(path: str, params: dict | None = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot reach API at {API_BASE}. Is `uvicorn api.main:app` running?")
        return None
    except Exception as e:
        st.warning(f"API error for {path}: {e}")
        return None


# Health
health = api_get("/health")
if health:
    c1, c2, c3 = st.columns(3)
    c1.metric("API", health.get("status", "?").upper())
    c2.metric("Database", health.get("database", "?"))
    c3.metric("Total runs", health.get("run_count", 0))

st.divider()

# ── Panel 1: Run status ──────────────────────────────────────────────────────
st.subheader("Recent pipeline runs")
runs = api_get("/api/v1/runs", {"limit": 20})
if runs:
    df = pd.DataFrame(runs)[["run_id", "sample_id", "replicate", "status", "created_at"]]
    df["status"] = df["status"].map({"completed": "✅ completed", "running": "🔄 running", "failed": "❌ failed"}).fillna(df["status"])
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No runs yet. Register a run via POST /api/v1/runs.")

st.divider()

# ── Panel 2: Concordance trend ───────────────────────────────────────────────
st.subheader("Concordance trend")
sample = st.text_input("Sample ID", value="HG001", key="conc_sample")
conc   = api_get("/api/v1/concordance", {"limit": 200})
if conc and sample:
    sample_runs = api_get("/api/v1/runs", {"sample_id": sample, "limit": 200})
    if sample_runs:
        run_map = {str(r["id"]): r["run_id"] for r in sample_runs}
        df_c = pd.DataFrame(conc)
        df_c = df_c[df_c["run_id"].astype(str).isin(run_map)].copy()
        df_c["run_label"] = df_c["run_id"].astype(str).map(run_map)
        df_c = df_c.sort_values("created_at")

        col_snv, col_indel = st.columns(2)
        for col, vtype, label, thr in [
            (col_snv,   "SNP",   "SNV",   0.98),
            (col_indel, "INDEL", "Indel", 0.95),
        ]:
            sub = df_c[df_c["variant_type"] == vtype]
            if sub.empty:
                col.info(f"No {label} data."); continue
            fig = go.Figure()
            for metric, colour in [("f1_score", "#1f77b4"), ("precision", "#ff7f0e"), ("recall", "#2ca02c")]:
                fig.add_trace(go.Scatter(x=sub["run_label"], y=sub[metric], mode="lines+markers",
                                         name=metric.replace("_", " ").title(), line=dict(color=colour)))
            fig.add_hline(y=thr, line_dash="dash", line_color="red", annotation_text=f"Threshold ({thr})")
            fig.update_layout(title=f"{label} — {sample}", yaxis=dict(range=[0.90, 1.005]),
                              height=320, margin=dict(t=50, b=30))
            col.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Panel 3: Reproducibility ─────────────────────────────────────────────────
st.subheader("VAF reproducibility")
repro = api_get("/api/v1/reproducibility", {"limit": 50})
if repro:
    df_r = pd.DataFrame(repro)
    sel  = st.selectbox("Sample", df_r["sample_id"].unique().tolist(), key="repro_sample")
    sub  = df_r[df_r["sample_id"] == sel].sort_values("created_at")
    if not sub.empty:
        latest = sub.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("ICC (latest)",      f"{latest['icc']:.4f}",       help="≥ 0.90 required")
        c2.metric("Median CV % (latest)", f"{latest['median_cv']:.2f}%", help="≤ 15% required")
        c3.metric("Overall pass", "✅ Yes" if latest["overall_pass"] else "❌ No")
else:
    st.info("No reproducibility results yet.")

st.divider()

# ── Panel 4: Active alerts ───────────────────────────────────────────────────
st.subheader("Active quality alerts")
alerts = api_get("/api/v1/alerts", {"unresolved_only": "true", "limit": 50})
if alerts:
    df_a = pd.DataFrame(alerts)
    if df_a.empty:
        st.success("No active alerts. All runs within tolerance.")
    else:
        icon = {"rejection": "🔴", "warning": "🟡", "info": "🔵"}
        df_a[""] = df_a["severity"].map(icon).fillna("⚪")
        st.dataframe(
            df_a[["", "alert_type", "metric", "variant_type", "value", "threshold", "message", "created_at"]],
            use_container_width=True, hide_index=True,
        )
else:
    st.success("No active alerts.")
