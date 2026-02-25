# This Streamlit app presents the results of automation risk analysis in a business-friendly dashboard.

# Import the necessary libraries
import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from scipy import stats

# Streamlit page configuration
st.set_page_config(
    page_title="AI and the Future of Work and Learning Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Filepath 
POSTINGS_CSV_DEFAULT = r"C:\Users\sunde\Downloads\Data Analyst Course\Capstone Projects\AI-and-the-Future-of-Work-and-Learning\processed\dashboard_data.csv"
ROLES_H2_CSV_DEFAULT = r"C:\Users\sunde\Downloads\Data Analyst Course\Capstone Projects\AI-and-the-Future-of-Work-and-Learning\processed\roles_h2_source.csv"
TOTAL_POSTINGS_DEFAULT = 50015

# Load CSV with caching 
@st.cache_data(show_spinner=False)
def load_csv(uploaded_file, path: str) -> pd.DataFrame:
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    return pd.read_csv(path)

# column validation 
def require_cols(df: pd.DataFrame, cols, label: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"{label}: Missing columns {missing}")
        st.stop()

# convert columns to numeric 
def to_num(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# Linear R² calculation for scatter plots
def linear_r2(x: np.ndarray, y: np.ndarray) -> float:
    x = x.reshape(-1, 1)
    m = LinearRegression().fit(x, y)
    return float(r2_score(y, m.predict(x)))

def one_sided_p_from_two_sided(t_stat, p_two, mean_x, mean_y, direction):
    """
    direction:
      - "less": mean_x < mean_y
      - "greater": mean_x > mean_y
    Matches your notebook logic.
    """
    if np.isnan(t_stat) or np.isnan(p_two):
        return np.nan
    if direction == "less":
        return (p_two / 2) if (mean_x < mean_y) else (1 - p_two / 2)
    if direction == "greater":
        return (p_two / 2) if (mean_x > mean_y) else (1 - p_two / 2)
    raise ValueError("direction must be 'less' or 'greater'")

# P-value formatting for display
def format_p(p):
    if pd.isna(p):
        return "nan"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"

# Risk bands for categorization 
def risk_band(series: pd.Series) -> pd.Series:
    # Bands are business-friendly; tweak thresholds if your score scale differs.
    # Assumes automation_risk_score is 0–1-ish. If it’s 0–100, adjust cutoffs.
    bins = [-np.inf, 0.33, 0.66, np.inf]
    labels = ["Low", "Medium", "High"]
    return pd.cut(series, bins=bins, labels=labels)

def safe_mean(x):
    return float(np.nanmean(x)) if len(x) else np.nan

def safe_median(x):
    return float(np.nanmedian(x)) if len(x) else np.nan

# CSV download helper 
def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# sidebar inputs and controls 
st.sidebar.title("Data Inputs")

# sidebar header 
postings_up = st.sidebar.file_uploader("Upload POSTINGS CSV (optional)", type=["csv"])
postings_path = st.sidebar.text_input("POSTINGS CSV path", value=POSTINGS_CSV_DEFAULT)

roles_up = st.sidebar.file_uploader("Upload ROLES-H2 CSV (optional)", type=["csv"])
roles_path = st.sidebar.text_input("ROLES-H2 CSV path", value=ROLES_H2_CSV_DEFAULT)

st.sidebar.divider()
st.sidebar.subheader("Reporting Controls")

total_postings = st.sidebar.number_input(
    "Total job postings (for match rate)",
    min_value=0,
    value=TOTAL_POSTINGS_DEFAULT,
    step=1
)

show_advanced = st.sidebar.toggle("Show advanced diagnostics", value=False)

st.sidebar.caption("Debug")
st.sidebar.write("Postings exists?", os.path.exists(postings_path.strip()))
st.sidebar.write("Roles-H2 exists?", os.path.exists(roles_path.strip()))

# Load and preprocess data
postings = load_csv(postings_up, postings_path.strip())
roles_h2 = load_csv(roles_up, roles_path.strip())

# Validate columns (NO row_id)
require_cols(
    postings,
    ["job_link", "job_title", "job_role_mapped",
     "human_centred_index", "task_repetition_level", "automation_risk_score"],
    "POSTINGS"
)
require_cols(
    roles_h2,
    ["skill_group", "automation_risk_score", "job_growth_rate"],
    "ROLES-H2"
)

# Numeric coercion
postings = to_num(postings, ["human_centred_index", "task_repetition_level", "automation_risk_score"])
roles_h2 = to_num(roles_h2, ["automation_risk_score", "job_growth_rate"])

# Deduplicate postings by job_link 
postings = postings.sort_values("job_link").drop_duplicates("job_link").copy()

# Full-case postings for H1 (your logic)
postings_h1 = postings.dropna(subset=[
    "job_role_mapped", "human_centred_index", "task_repetition_level", "automation_risk_score"
]).copy()

# H2 datasets: drop NA 
h2a = roles_h2.dropna(subset=["automation_risk_score"]).copy()
h2b = roles_h2.dropna(subset=["job_growth_rate"]).copy()

# Add risk bands
postings_h1["risk_band"] = risk_band(postings_h1["automation_risk_score"])
h2a["risk_band"] = risk_band(h2a["automation_risk_score"])

# Header 
st.title("Automation Risk vs Skills — Business Dashboard")

match_rate = (len(postings_h1) / total_postings) if total_postings else np.nan

# KPI row
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Matched postings (H1)", f"{len(postings_h1):,}")
k2.metric("Match rate", "-" if np.isnan(match_rate) else f"{match_rate*100:.1f}%")
k3.metric("Avg automation risk (H1)", f"{safe_mean(postings_h1['automation_risk_score']):.3f}")
k4.metric("Median automation risk (H1)", f"{safe_median(postings_h1['automation_risk_score']):.3f}")
k5.metric("Roles in H2 file", f"{len(roles_h2):,}")

st.info(
    f"**Hypothesis results are assumed correct** and this dashboard presents them in a business-friendly way.\n\n"
    f"- **H1** uses posting-level matched rows: **{len(postings_h1):,}** "
    f"({('-' if np.isnan(match_rate) else f'{match_rate*100:.1f}%')} of {total_postings:,}).\n"
    f"- **H2** uses role-level groups from `roles_h2_source.csv` (same as your hypothesis tests)."
)

# role filter 
with st.sidebar:
    st.subheader("Global Filters")

    # Role filter (H1)
    role_options = ["All"] + sorted([r for r in postings_h1["job_role_mapped"].dropna().unique().tolist()])
    sel_role = st.selectbox("Job role (H1)", role_options, index=0)

    # Risk band filter (H1)
    band_options = ["All", "Low", "Medium", "High"]
    sel_band = st.multiselect("Risk band (H1)", band_options, default=["All"])

    # Numeric range (H1)
    rmin, rmax = st.slider("Automation risk range (H1)", 0.0, 1.0, (0.0, 1.0), 0.01)

# Apply filters to postings_h1
f_postings = postings_h1.copy()
if sel_role != "All":
    f_postings = f_postings[f_postings["job_role_mapped"] == sel_role]
if "All" not in sel_band:
    f_postings = f_postings[f_postings["risk_band"].astype(str).isin(sel_band)]
f_postings = f_postings[
    (f_postings["automation_risk_score"] >= rmin) & (f_postings["automation_risk_score"] <= rmax)
]

# Tabs for different views
tab_exec, tab_h1, tab_h2, tab_quality = st.tabs([
    "Executive View",
    "H1 — Postings",
    "H2 — Roles (Hypothesis Tests)",
    "Data Quality",
])

# Executive summary tab with key charts
with tab_exec:
    st.subheader("Executive View")

    left, right = st.columns([1.1, 0.9])

    with left:
        st.markdown("#### Risk distribution (filtered H1)")
        if len(f_postings) == 0:
            st.warning("No postings match the selected filters.")
        else:
            fig = px.histogram(
                f_postings,
                x="automation_risk_score",
                nbins=30,
                title="Distribution of automation risk",
            )
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("#### Risk band split (filtered H1)")
        if len(f_postings) > 0:
            band_counts = f_postings["risk_band"].value_counts(dropna=False).rename_axis("risk_band").reset_index(name="count")
            fig = px.pie(
                band_counts,
                names="risk_band",
                values="count",
                title="Low vs Medium vs High",
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.markdown("#### Top roles by average risk (H1)")
    if len(postings_h1) > 0:
        top_roles = (
            postings_h1.dropna(subset=["job_role_mapped", "automation_risk_score"])
            .groupby("job_role_mapped", as_index=False)
            .agg(
                avg_risk=("automation_risk_score", "mean"),
                n=("job_link", "count")
            )
            .sort_values(["avg_risk", "n"], ascending=[False, False])
            .head(15)
        )
        fig = px.bar(top_roles, x="job_role_mapped", y="avg_risk", hover_data=["n"], title="Top 15 roles by average automation risk")
        fig.update_layout(xaxis_title="Role", yaxis_title="Avg automation risk")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No H1 postings available.")

    st.divider()

    st.markdown("#### What the hypothesis results imply (plain English)")
    st.write(
        "- **H1:** As human-centred work increases, automation risk tends to **decrease**; as task repetition increases, automation risk tends to **increase**.\n"
        "- **H2:** Roles blending **Tech + Domain** skills show **lower automation risk** and **higher growth** than **Technical-only** roles (per your tests)."
    )

# H1 hypothesis details 
with tab_h1:
    st.subheader("Hypothesis 1 — Posting-level (with filters applied)")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filtered postings", f"{len(f_postings):,}")
    c2.metric("Avg risk", "-" if len(f_postings)==0 else f"{safe_mean(f_postings['automation_risk_score']):.3f}")
    c3.metric("Avg human-centred", "-" if len(f_postings)==0 else f"{safe_mean(f_postings['human_centred_index']):.3f}")
    c4.metric("Avg repetition", "-" if len(f_postings)==0 else f"{safe_mean(f_postings['task_repetition_level']):.3f}")

    left, right = st.columns(2)

    with left:
        st.markdown("#### H1a: Human-centred index vs automation risk")
        if len(f_postings) >= 3:
            r2 = linear_r2(
                f_postings["human_centred_index"].to_numpy(),
                f_postings["automation_risk_score"].to_numpy()
            )
            st.caption(f"Linear fit R² = {r2:.3f}")
        fig = px.scatter(
            f_postings,
            x="human_centred_index",
            y="automation_risk_score",
            trendline="ols",
            title="Human-centred index vs Automation risk",
            hover_data=["job_title", "job_role_mapped", "job_link"],
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("#### H1b: Task repetition vs automation risk")
        if len(f_postings) >= 3:
            r2 = linear_r2(
                f_postings["task_repetition_level"].to_numpy(),
                f_postings["automation_risk_score"].to_numpy()
            )
            st.caption(f"Linear fit R² = {r2:.3f}")
        fig = px.scatter(
            f_postings,
            x="task_repetition_level",
            y="automation_risk_score",
            trendline="ols",
            title="Task repetition vs Automation risk",
            hover_data=["job_title", "job_role_mapped", "job_link"],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.markdown("#### Drill-down: postings table (filtered)")
    show_cols = ["job_title", "job_role_mapped", "human_centred_index", "task_repetition_level", "automation_risk_score", "job_link"]
    st.dataframe(
        f_postings[show_cols].sort_values("automation_risk_score", ascending=False),
        use_container_width=True,
        height=420
    )

    st.download_button(
        "Download filtered postings as CSV",
        data=df_to_csv_bytes(f_postings[show_cols]),
        file_name="filtered_postings.csv",
        mime="text/csv"
    )

# H2 hypothesis details
with tab_h2:
    st.subheader("Hypothesis 2 — Role-level (matches notebook)")

    # Role counts by group
    st.markdown("#### Role counts by skill group")
    counts = roles_h2["skill_group"].value_counts()
    st.dataframe(counts.rename("count"), use_container_width=True)

    st.divider()

    # H2a (risk): Tech+Domain < Technical-only
    st.markdown("### H2a — Automation risk by skill group")
    risk_td = h2a.loc[h2a["skill_group"] == "Tech+Domain", "automation_risk_score"].values
    risk_to = h2a.loc[h2a["skill_group"] == "Technical-only", "automation_risk_score"].values

    means_risk = (
        h2a.groupby("skill_group")["automation_risk_score"]
        .mean()
        .reindex(["Technical-only", "Tech+Domain"])
        .reset_index()
    )
    fig = px.bar(
        means_risk,
        x="skill_group",
        y="automation_risk_score",
        title="Average automation risk (H2a)"
    )
    st.plotly_chart(fig, use_container_width=True)

    if len(risk_td) >= 2 and len(risk_to) >= 2:
        t_stat, p_two = stats.ttest_ind(risk_td, risk_to, equal_var=False)
        p_one = one_sided_p_from_two_sided(
            t_stat, p_two,
            np.nanmean(risk_td), np.nanmean(risk_to),
            direction="less"
        )

        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Mean risk (Tech+Domain)", f"{np.nanmean(risk_td):.3f}")
        a2.metric("Mean risk (Technical-only)", f"{np.nanmean(risk_to):.3f}")
        a3.metric("t-stat", f"{t_stat:.3f}")
        a4.metric("One-sided p", format_p(p_one))

        st.success(
            "Interpretation: Tech+Domain roles show **lower automation risk** than Technical-only roles "
            "(based on your one-sided test direction)."
        )
    else:
        st.warning("Not enough roles in both groups for H2a t-test (need >=2 per group).")

    st.divider()

    # H2b (growth): Tech+Domain > Technical-only
    st.markdown("### H2b — Job growth rate by skill group")
    growth_td = h2b.loc[h2b["skill_group"] == "Tech+Domain", "job_growth_rate"].values
    growth_to = h2b.loc[h2b["skill_group"] == "Technical-only", "job_growth_rate"].values

    means_growth = (
        h2b.groupby("skill_group")["job_growth_rate"]
        .mean()
        .reindex(["Technical-only", "Tech+Domain"])
        .reset_index()
    )
    fig = px.bar(
        means_growth,
        x="skill_group",
        y="job_growth_rate",
        title="Average job growth rate (H2b)"
    )
    st.plotly_chart(fig, use_container_width=True)

    if len(growth_td) >= 2 and len(growth_to) >= 2:
        t_stat, p_two = stats.ttest_ind(growth_td, growth_to, equal_var=False)
        p_one = one_sided_p_from_two_sided(
            t_stat, p_two,
            np.nanmean(growth_td), np.nanmean(growth_to),
            direction="greater"
        )

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Mean growth (Tech+Domain)", f"{np.nanmean(growth_td):.3f}")
        b2.metric("Mean growth (Technical-only)", f"{np.nanmean(growth_to):.3f}")
        b3.metric("t-stat", f"{t_stat:.3f}")
        b4.metric("One-sided p", format_p(p_one))

        st.success(
            "Interpretation: Tech+Domain roles show **higher growth** than Technical-only roles "
            "(based on your one-sided test direction)."
        )
    else:
        st.warning("Not enough roles in both groups for H2b t-test (need >=2 per group).")

    st.divider()

    st.markdown("#### Drill-down: H2 role table")
    st.dataframe(roles_h2, use_container_width=True, height=420)
    st.download_button(
        "Download H2 roles as CSV",
        data=df_to_csv_bytes(roles_h2),
        file_name="roles_h2.csv",
        mime="text/csv"
    )

# Data quality and diagnostics
with tab_quality:
    st.subheader("Data Quality")

    st.markdown("### Postings — missingness (key columns)")
    cols = ["job_role_mapped", "human_centred_index", "task_repetition_level", "automation_risk_score"]
    miss = pd.DataFrame({
        "column": cols,
        "missing": [int(postings[c].isna().sum()) for c in cols],
        "missing_%": [float(postings[c].isna().mean() * 100) for c in cols],
    })
    st.dataframe(miss, use_container_width=True)

    st.markdown("### Postings — dedupe + coverage")
    d1, d2, d3 = st.columns(3)
    d1.metric("Raw postings rows", f"{len(load_csv(postings_up, postings_path.strip())):,}")
    d2.metric("After dedupe(job_link)", f"{len(postings):,}")
    d3.metric("H1 full-case rows", f"{len(postings_h1):,}")

    st.divider()

    st.markdown("### Roles-H2 preview")
    st.dataframe(roles_h2.head(50), use_container_width=True)

    if show_advanced:
        st.divider()
        st.markdown("### Advanced diagnostics")
        st.write("Postings dtypes:")
        st.write(postings.dtypes)
        st.write("Roles-H2 dtypes:")
        st.write(roles_h2.dtypes)