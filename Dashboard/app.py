import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from scipy import stats

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Future Skills & Automation Risk", layout="wide")

DATA_CSV_DEFAULT = r"C:\Users\sunde\Downloads\Data Analyst Course\Capstone Projects\AI-and-the-Future-of-Work-and-Learning\processed\dashboard_data.csv"
TOTAL_POSTINGS_DEFAULT = 50015

# =========================
# HELPERS
# =========================
@st.cache_data(show_spinner=False)
def load_csv(uploaded_file, path: str) -> pd.DataFrame:
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    return pd.read_csv(path)

def require_cols(df: pd.DataFrame, cols, label: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"{label}: Missing columns {missing}")
        st.stop()

def to_num(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def risk_band(score: pd.Series) -> pd.Series:
    # Assumes 0–1. If your risk is 0–100, change to bins=[-inf, 33, 66, inf]
    bins = [-np.inf, 0.33, 0.66, np.inf]
    labels = ["Low", "Medium", "High"]
    return pd.cut(score, bins=bins, labels=labels)

def safe_mean(x):
    return float(np.nanmean(x)) if len(x) else np.nan

def safe_median(x):
    return float(np.nanmedian(x)) if len(x) else np.nan

def format_p(p):
    if pd.isna(p):
        return "nan"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"

def one_sided_p_from_two_sided(t_stat, p_two, mean_x, mean_y, direction):
    """
    Matches your notebook logic.
    direction:
      - "less": mean_x < mean_y
      - "greater": mean_x > mean_y
    """
    if np.isnan(t_stat) or np.isnan(p_two):
        return np.nan
    if direction == "less":
        return (p_two / 2) if (mean_x < mean_y) else (1 - p_two / 2)
    if direction == "greater":
        return (p_two / 2) if (mean_x > mean_y) else (1 - p_two / 2)
    raise ValueError("direction must be 'less' or 'greater'")

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# =========================
# SIDEBAR — ONE FILE
# =========================
st.sidebar.title("Data (Single Combined File)")

data_up = st.sidebar.file_uploader("Upload combined dashboard_data.csv (optional)", type=["csv"])
data_path = st.sidebar.text_input("CSV path", value=DATA_CSV_DEFAULT)

st.sidebar.caption("Debug")
st.sidebar.write("File exists?", os.path.exists(data_path.strip()))

total_postings = st.sidebar.number_input(
    "Total job postings (for match rate)",
    min_value=0,
    value=TOTAL_POSTINGS_DEFAULT,
    step=1
)

# =========================
# TEMPLATE DOWNLOAD (OPTION 2)
# =========================
st.sidebar.divider()
st.sidebar.subheader("Download Template")
st.sidebar.caption("One file can contain both posting rows and H2 rows (leave unused fields blank).")

template = pd.DataFrame(columns=[
    # Posting-level fields
    "job_link",
    "job_title",
    "job_role_mapped",
    "human_centred_index",
    "task_repetition_level",
    "automation_risk_score",
    # H2 fields
    "skill_group",
    "job_growth_rate",
    # Optional: helps splitting if you include it
    "source_table"  # e.g., "postings" or "roles_h2"
])
st.sidebar.download_button(
    "Download Combined Template CSV",
    data=template.to_csv(index=False),
    file_name="combined_dashboard_template.csv",
    mime="text/csv"
)

# Curriculum (optional)
st.sidebar.divider()
st.sidebar.subheader("Curriculum Gap Scan (optional)")
curr_up = st.sidebar.file_uploader("Upload curriculum CSV", type=["csv"])
st.sidebar.caption("Expected column: skill_or_module")

# =========================
# LOAD DATA
# =========================
df = load_csv(data_up, data_path.strip())

# We need a combined schema so we can slice safely
# (Some rows will be postings, some rows will be H2.)
REQUIRED_COMBINED_COLS = [
    "automation_risk_score",  # used by both analyses
    # posting-level
    "job_link", "job_title", "job_role_mapped",
    "human_centred_index", "task_repetition_level",
    # H2-level
    "skill_group", "job_growth_rate"
]
require_cols(df, REQUIRED_COMBINED_COLS, "COMBINED DATASET")

# Convert numeric columns safely
df = to_num(df, ["human_centred_index", "task_repetition_level", "automation_risk_score", "job_growth_rate"])

# =========================
# SPLIT THE ONE FILE INTO TWO "SLICES"
# =========================
# If you have source_table, use it. Otherwise infer by which key fields exist.
if "source_table" in df.columns:
    postings_raw = df[df["source_table"].astype(str).str.lower().str.contains("post")].copy()
    roles_raw = df[df["source_table"].astype(str).str.lower().str.contains("role")].copy()
else:
    postings_raw = df[df["job_link"].notna()].copy()
    roles_raw = df[df["skill_group"].notna()].copy()

# -------------------------
# Postings slice (H1)
# -------------------------
postings_raw = postings_raw.sort_values("job_link").drop_duplicates("job_link").copy()

postings_h1 = postings_raw.dropna(subset=[
    "job_role_mapped", "human_centred_index", "task_repetition_level", "automation_risk_score"
]).copy()

postings_h1["risk_band"] = risk_band(postings_h1["automation_risk_score"])

# AI-resistance proxy (transparent)
postings_h1["resistance_score"] = (
    postings_h1["human_centred_index"].rank(pct=True) +
    (1 - postings_h1["task_repetition_level"].rank(pct=True)) +
    (1 - postings_h1["automation_risk_score"].rank(pct=True))
) / 3

# -------------------------
# H2 slice
# -------------------------
roles_h2 = roles_raw.dropna(subset=["skill_group"]).copy()
h2a = roles_h2.dropna(subset=["automation_risk_score"]).copy()
h2b = roles_h2.dropna(subset=["job_growth_rate"]).copy()

# =========================
# HEADER / KPIs
# =========================
st.title("Future Skills & Automation Risk — Business Dashboard")

match_rate = (len(postings_h1) / total_postings) if total_postings else np.nan

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Matched postings (H1)", f"{len(postings_h1):,}")
k2.metric("Match rate", "-" if np.isnan(match_rate) else f"{match_rate*100:.1f}%")
k3.metric("Avg automation risk (H1)", f"{safe_mean(postings_h1['automation_risk_score']):.3f}")
k4.metric("Avg AI-resistance (H1)", f"{safe_mean(postings_h1['resistance_score']):.3f}")
k5.metric("H2 rows detected", f"{len(roles_h2):,}")

tabs = st.tabs([
    "Overview",
    "Future Skill Demand",
    "Job Vulnerability",
    "H2 Skill Groups",
    "Curriculum Gap Scan",
    "Ethics & Data Quality",
])

# =========================
# TAB: OVERVIEW
# =========================
with tabs[0]:
    st.subheader("Overview")

    if len(postings_h1) == 0:
        st.warning("No posting-level rows detected (job_link missing / source_table not matching).")
    else:
        a, b = st.columns(2)
        with a:
            fig = px.histogram(postings_h1, x="automation_risk_score", nbins=30, title="Automation risk distribution (postings)")
            st.plotly_chart(fig, use_container_width=True)

        with b:
            band_counts = postings_h1["risk_band"].value_counts().rename_axis("risk_band").reset_index(name="count")
            fig = px.pie(band_counts, names="risk_band", values="count", title="Risk bands (Low / Medium / High)")
            st.plotly_chart(fig, use_container_width=True)

# =========================
# TAB: FUTURE SKILL DEMAND
# =========================
with tabs[1]:
    st.subheader("Future Skill Demand")

    if len(postings_h1) == 0:
        st.warning("No posting-level rows detected, so future skill demand proxy cannot be computed.")
    else:
        top_resistant = (
            postings_h1.groupby("job_role_mapped", as_index=False)
            .agg(
                postings=("job_link", "count"),
                avg_resistance=("resistance_score", "mean"),
                avg_risk=("automation_risk_score", "mean"),
                avg_human=("human_centred_index", "mean"),
                avg_repeat=("task_repetition_level", "mean"),
            )
            .sort_values(["avg_resistance", "postings"], ascending=[False, False])
            .head(15)
        )

        fig = px.bar(
            top_resistant,
            x="job_role_mapped",
            y="avg_resistance",
            hover_data=["postings", "avg_risk", "avg_human", "avg_repeat"],
            title="Most AI-resistant roles (proxy for resilient skill demand)"
        )
        st.plotly_chart(fig, use_container_width=True)

# =========================
# TAB: JOB VULNERABILITY
# =========================
with tabs[2]:
    st.subheader("Job Vulnerability (role level)")

    if len(postings_h1) == 0:
        st.warning("No posting-level rows detected, so role vulnerability cannot be computed.")
    else:
        vuln = (
            postings_h1.groupby("job_role_mapped", as_index=False)
            .agg(
                postings=("job_link", "count"),
                avg_risk=("automation_risk_score", "mean"),
                avg_resistance=("resistance_score", "mean")
            )
            .sort_values(["avg_risk", "postings"], ascending=[False, False])
        )
        vuln["risk_band"] = risk_band(vuln["avg_risk"]).astype(str)

        fig = px.scatter(
            vuln,
            x="avg_resistance",
            y="avg_risk",
            size="postings",
            color="risk_band",
            hover_data=["job_role_mapped", "postings"],
            title="Role positioning: AI-resistance vs automation risk"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(vuln, use_container_width=True, height=420)

# =========================
# TAB: H2 SKILL GROUPS
# =========================
with tabs[3]:
    st.subheader("H2: Skill-group comparisons (from the same combined file)")

    if len(roles_h2) == 0:
        st.warning("No H2 rows detected (skill_group missing / source_table not matching).")
    else:
        counts = roles_h2["skill_group"].value_counts().rename_axis("skill_group").reset_index(name="count")
        st.markdown("#### Role counts by skill_group")
        st.dataframe(counts, use_container_width=True)

        means = (
            roles_h2.groupby("skill_group", as_index=False)
            .agg(
                mean_risk=("automation_risk_score", "mean"),
                mean_growth=("job_growth_rate", "mean")
            )
            .reindex(columns=["skill_group", "mean_risk", "mean_growth"])
        )

        a, b = st.columns(2)
        with a:
            fig = px.bar(means, x="skill_group", y="mean_risk", title="Mean automation risk by skill group")
            st.plotly_chart(fig, use_container_width=True)
        with b:
            fig = px.bar(means, x="skill_group", y="mean_growth", title="Mean job growth by skill group")
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.markdown("#### Hypothesis tests (same notebook logic)")

        # H2a: risk Tech+Domain < Technical-only
        risk_td = h2a.loc[h2a["skill_group"] == "Tech+Domain", "automation_risk_score"].values
        risk_to = h2a.loc[h2a["skill_group"] == "Technical-only", "automation_risk_score"].values

        if len(risk_td) >= 2 and len(risk_to) >= 2:
            t_stat, p_two = stats.ttest_ind(risk_td, risk_to, equal_var=False)
            p_one = one_sided_p_from_two_sided(t_stat, p_two, np.nanmean(risk_td), np.nanmean(risk_to), "less")
            st.code(
                "H2a (Risk) — Tech+Domain < Technical-only\n"
                f"Mean risk Tech+Domain   : {np.nanmean(risk_td):.4f}\n"
                f"Mean risk Technical-only: {np.nanmean(risk_to):.4f}\n"
                f"t = {t_stat:.3f}, one-sided p = {format_p(p_one)}"
            )
        else:
            st.info("H2a: Not enough data for test (need >=2 per group).")

        # H2b: growth Tech+Domain > Technical-only
        growth_td = h2b.loc[h2b["skill_group"] == "Tech+Domain", "job_growth_rate"].values
        growth_to = h2b.loc[h2b["skill_group"] == "Technical-only", "job_growth_rate"].values

        if len(growth_td) >= 2 and len(growth_to) >= 2:
            t_stat, p_two = stats.ttest_ind(growth_td, growth_to, equal_var=False)
            p_one = one_sided_p_from_two_sided(t_stat, p_two, np.nanmean(growth_td), np.nanmean(growth_to), "greater")
            st.code(
                "H2b (Growth) — Tech+Domain > Technical-only\n"
                f"Mean growth Tech+Domain   : {np.nanmean(growth_td):.4f}\n"
                f"Mean growth Technical-only: {np.nanmean(growth_to):.4f}\n"
                f"t = {t_stat:.3f}, one-sided p = {format_p(p_one)}"
            )
        else:
            st.info("H2b: Not enough data for test (need >=2 per group).")

# =========================
# TAB: CURRICULUM GAP SCAN
# =========================
with tabs[4]:
    st.subheader("Curriculum Gap Scan (optional, transparent)")

    if len(postings_h1) == 0:
        st.warning("No posting-level rows detected, so recommended focus areas cannot be computed.")
    else:
        focus = (
            postings_h1.groupby("job_role_mapped", as_index=False)
            .agg(postings=("job_link", "count"), avg_resistance=("resistance_score", "mean"))
            .sort_values(["avg_resistance", "postings"], ascending=[False, False])
            .head(15)
            .rename(columns={"job_role_mapped": "recommended_focus_area"})
        )

        if curr_up is None:
            st.info("Upload curriculum CSV to compare. Showing recommended focus areas only.")
            st.dataframe(focus, use_container_width=True)
        else:
            curr = pd.read_csv(curr_up)
            require_cols(curr, ["skill_or_module"], "CURRICULUM")
            curr["skill_or_module"] = curr["skill_or_module"].astype(str).str.strip()
            curr_set = set(curr["skill_or_module"].str.lower())

            focus["covered_in_curriculum"] = focus["recommended_focus_area"].str.lower().apply(
                lambda x: any(x in c or c in x for c in curr_set)
            )

            a, b = st.columns(2)
            with a:
                st.markdown("#### Potential gaps")
                st.dataframe(focus[~focus["covered_in_curriculum"]], use_container_width=True)
            with b:
                st.markdown("#### Appears covered")
                st.dataframe(focus[focus["covered_in_curriculum"]], use_container_width=True)

# =========================
# TAB: ETHICS & DATA QUALITY
# =========================
with tabs[5]:
    st.subheader("Ethics & Data Quality")

    st.markdown("### Ethical use")
    st.write(
        "- Shows **patterns in the dataset**, not predictions about individuals.\n"
        "- Risk bands are for **planning**, not labelling people.\n"
        "- Gap scan uses **transparent string matching**, not black-box inference.\n"
    )

    st.markdown("### Missingness (key columns)")
    key_cols = [
        "job_link", "job_title", "job_role_mapped",
        "human_centred_index", "task_repetition_level", "automation_risk_score",
        "skill_group", "job_growth_rate"
    ]
    miss = pd.DataFrame({
        "column": key_cols,
        "missing": [int(df[c].isna().sum()) for c in key_cols],
        "missing_%": [float(df[c].isna().mean() * 100) for c in key_cols],
    })
    st.dataframe(miss, use_container_width=True)

    st.markdown("### Preview of combined file (first 50 rows)")
    st.dataframe(df.head(50), use_container_width=True)

    st.download_button(
        "Download combined file (as loaded)",
        data=df_to_csv_bytes(df),
        file_name="dashboard_data_export.csv",
        mime="text/csv"
    )