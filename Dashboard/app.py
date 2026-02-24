import streamlit as st
import pandas as pd
import numpy as np

import plotly.express as px
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import train_test_split

st.set_page_config(page_title="Automation Risk & Skills Dashboard", layout="wide")

# -----------------------------
# Column map (your schema)
# -----------------------------
COL = {
    "link": "job_link",
    "title": "job_title",
    "role": "job_role_mapped",
    "human": "human_centred_index",
    "repeat": "task_repetition_level",
    "risk": "automation_risk_score",
    "growth": "job_growth_rate",
    "domain": "domain_level",
    "ai": "ai_dependency",
}

TOTAL_POSTINGS_DEFAULT = 50015  # from your write-up

# -----------------------------
# Helpers
# -----------------------------
def require_cols(df: pd.DataFrame, cols: list[str]):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

@st.cache_data(show_spinner=False)
def load_csv(uploaded_file, local_path: str | None):
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    if local_path:
        return pd.read_csv(local_path)
    return None

def dedupe(df: pd.DataFrame, key: str):
    before = len(df)
    out = df.drop_duplicates(subset=[key]).copy()
    after = len(out)
    return out, before, after, before - after

def to_num(df: pd.DataFrame, cols: list[str]):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def linear_r2(x: np.ndarray, y: np.ndarray) -> float:
    x = x.reshape(-1, 1)
    m = LinearRegression()
    m.fit(x, y)
    yhat = m.predict(x)
    return float(r2_score(y, yhat))

def pct(x):
    return "—" if pd.isna(x) else f"{x*100:.1f}%"

def build_h2_group(domain_level: pd.Series) -> pd.Series:
    """
    H2 grouping logic:
    - domain_level missing/low => Tech-only
    - otherwise => Tech+Domain
    Works whether domain_level is numeric or text.
    """
    s = domain_level.copy()

    if pd.api.types.is_numeric_dtype(s):
        return np.where(s.fillna(0) > 0, "Tech+Domain", "Tech-only")

    s2 = s.astype(str).str.strip().str.lower()
    tech_only_tokens = {"none", "no", "n/a", "na", "0", "low", "basic", "unknown", "nan"}
    return np.where(s2.isin(tech_only_tokens), "Tech-only", "Tech+Domain")

# -----------------------------
# Sidebar: input
# -----------------------------
st.sidebar.title("Controls")

uploaded = st.sidebar.file_uploader("Upload your merged+cleaned CSV", type=["csv"])

# ✅ your path prefilled (you can edit in the UI)
default_path = r"C:\Users\sunde\Downloads\Data Analyst Course\Capstone Projects\AI-and-the-Future-of-Work-and-Learning\processed\powerbi_dashboard.csv"
local_path = st.sidebar.text_input("...or load from local path", value=default_path)

df_raw = load_csv(uploaded, local_path.strip() or None)
if df_raw is None:
    st.info("Upload a CSV (or provide a valid local path) to start.")
    st.stop()

require_cols(df_raw, list(COL.values()))

# Dedupe for transparency
df, n_before, n_after, n_removed = dedupe(df_raw, COL["link"])

# Coerce numerics
df = to_num(df, [COL["human"], COL["repeat"], COL["risk"], COL["growth"], COL["ai"]])

# Build H2 group
df["h2_group"] = build_h2_group(df[COL["domain"]])

# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.subheader("Filters")

total_postings = st.sidebar.number_input(
    "Total job postings (for match-rate display)",
    min_value=0,
    value=TOTAL_POSTINGS_DEFAULT,
    step=1
)

roles = ["All"] + sorted(df[COL["role"]].dropna().unique().tolist())
role_choice = st.sidebar.selectbox("Mapped role", roles, index=0)

h2_groups = ["All"] + sorted(df["h2_group"].dropna().unique().tolist())
h2_choice = st.sidebar.selectbox("H2 group", h2_groups, index=0)

# AI dependency filter
ai_vals = df[COL["ai"]].to_numpy()
ai_min = float(np.nanmin(ai_vals)) if np.isfinite(np.nanmin(ai_vals)) else 0.0
ai_max = float(np.nanmax(ai_vals)) if np.isfinite(np.nanmax(ai_vals)) else 0.0

if np.isfinite(ai_min) and np.isfinite(ai_max) and ai_min != ai_max:
    ai_range = st.sidebar.slider("AI dependency range", ai_min, ai_max, (ai_min, ai_max))
else:
    ai_range = (ai_min, ai_max)

df_f = df.copy()
if role_choice != "All":
    df_f = df_f[df_f[COL["role"]] == role_choice]
if h2_choice != "All":
    df_f = df_f[df_f["h2_group"] == h2_choice]
if np.isfinite(ai_range[0]) and np.isfinite(ai_range[1]) and (ai_min != ai_max):
    df_f = df_f[df_f[COL["ai"]].between(ai_range[0], ai_range[1], inclusive="both")]

# Sidebar data snapshot
st.sidebar.subheader("Data snapshot")
st.sidebar.metric("Rows (raw)", f"{n_before:,}")
st.sidebar.metric("Rows (deduped)", f"{n_after:,}")
st.sidebar.metric("Duplicates removed", f"{n_removed:,}")

matched = len(df_f)
match_rate = (matched / total_postings) if total_postings else np.nan
st.sidebar.metric("Matched sample (filtered)", f"{matched:,}")
st.sidebar.metric("Match rate", pct(match_rate))

# -----------------------------
# Header + limitation rationale
# -----------------------------
st.title("Automation Risk vs Skills — Dashboard (Evidence + Transparency)")

st.warning(
    f"**Data limitation:** analyses here are based on the matched subset. "
    f"Current filtered sample: **{matched:,}** postings "
    f"(**{pct(match_rate)}** of {total_postings:,}). "
    "Patterns may look weaker and may not generalise to the full job market."
)

tabs = st.tabs([
    "Overview",
    "Hypothesis 1: Human-centred skills",
    "Hypothesis 2: Tech + Domain",
    "ML Prototype",
    "Data Quality & Transparency",
])

# -----------------------------
# Tab 1: Overview
# -----------------------------
with tabs[0]:
    st.subheader("Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sample size", f"{len(df_f):,}")
    c2.metric("Avg automation risk", f"{df_f[COL['risk']].mean():.3f}" if len(df_f) else "—")
    c3.metric("Avg job growth", f"{df_f[COL['growth']].mean():.3f}" if len(df_f) else "—")
    c4.metric("Avg AI dependency", f"{df_f[COL['ai']].mean():.3f}" if len(df_f) else "—")

    left, right = st.columns(2)
    with left:
        fig = px.histogram(
            df_f.dropna(subset=[COL["risk"]]),
            x=COL["risk"],
            nbins=30,
            title="Automation risk distribution",
        )
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = px.histogram(
            df_f.dropna(subset=[COL["growth"]]),
            x=COL["growth"],
            nbins=30,
            title="Job growth distribution",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        """
**Interpretation guidance**
- Results reflect only postings that could be matched to the automation-risk dataset.
- Duplicates were removed using unique job links to avoid inflated counts.
- Weak relationships can reflect both true weak effects and missing structural factors (industry dynamics, job design, tech adoption).
        """
    )

# -----------------------------
# Tab 2: Hypothesis 1
# -----------------------------
with tabs[1]:
    st.subheader("Hypothesis 1 — Human-centred skills and automation risk")

    d1 = df_f.dropna(subset=[COL["human"], COL["risk"]]).copy()
    d2 = df_f.dropna(subset=[COL["repeat"], COL["risk"]]).copy()

    colA, colB = st.columns(2)

    with colA:
        st.markdown("### H1a: Human-centred skills vs automation risk")
        if len(d1) >= 3:
            r2 = linear_r2(d1[COL["human"]].to_numpy(), d1[COL["risk"]].to_numpy())
            st.caption(f"Linear fit R² = {r2:.3f}")
        fig = px.scatter(
            d1,
            x=COL["human"],
            y=COL["risk"],
            trendline="ols",
            title="Human-centred skills vs Automation risk",
            hover_data=[COL["title"], COL["role"], COL["link"], "h2_group"],
        )
        st.plotly_chart(fig, use_container_width=True)

    with colB:
        st.markdown("### H1b: Task repetition vs automation risk")
        if len(d2) >= 3:
            r2 = linear_r2(d2[COL["repeat"]].to_numpy(), d2[COL["risk"]].to_numpy())
            st.caption(f"Linear fit R² = {r2:.3f}")
        fig = px.scatter(
            d2,
            x=COL["repeat"],
            y=COL["risk"],
            trendline="ols",
            title="Task repetition vs Automation risk",
            hover_data=[COL["title"], COL["role"], COL["link"], "h2_group"],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.info(
        "**Business implications**\n\n"
        "- Higher human-centred skill demand may align with *slightly* lower automation risk, but explanatory power is weak.\n"
        "- Task repetition shows little predictive value here.\n"
        "- Curriculum: embed communication, collaboration, problem-solving, and creativity within discipline/technical contexts."
    )

# -----------------------------
# Tab 3: Hypothesis 2
# -----------------------------
with tabs[2]:
    st.subheader("Hypothesis 2 — Digital + Domain skills")

    d = df_f.dropna(subset=["h2_group", COL["risk"], COL["growth"]]).copy()
    if len(d) == 0:
        st.info("No data available after current filters.")
    else:
        grp = d.groupby("h2_group", dropna=False).agg(
            avg_risk=(COL["risk"], "mean"),
            avg_growth=(COL["growth"], "mean"),
            n=(COL["risk"], "size"),
        ).reset_index()

        a, b = st.columns(2)
        with a:
            fig = px.bar(
                grp,
                x="h2_group",
                y="avg_risk",
                title="H2a: Avg automation risk (Tech-only vs Tech+Domain)",
                text="n",
            )
            st.plotly_chart(fig, use_container_width=True)

        with b:
            fig = px.bar(
                grp,
                x="h2_group",
                y="avg_growth",
                title="H2b: Avg job growth (Tech-only vs Tech+Domain)",
                text="n",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.caption("Grouping note: Tech+Domain is inferred from domain_level (see Data Quality tab).")

        st.info(
            "**Business implications**\n\n"
            "- Tech+Domain roles often show lower automation risk, suggesting better long-term stability.\n"
            "- Job growth differences may appear visually, but may not be statistically reliable in this sample.\n"
            "- Curriculum strategy: prioritise hybrid pathways (data+healthcare, AI+finance, digital+sustainability)."
        )

# -----------------------------
# Tab 4: ML Prototype
# -----------------------------
with tabs[3]:
    st.subheader("Machine Learning prototype (proof of concept)")

    st.markdown(
        """
This checks whether automation risk can be predicted from a small set of variables.
If performance is low, it supports your rationale that automation risk depends on many structural factors beyond skills.
        """
    )

    features = st.multiselect(
        "Choose features (predictors)",
        options=[COL["human"], COL["repeat"], COL["growth"], COL["ai"]],
        default=[COL["human"], COL["repeat"]],
    )

    run = st.button("Run baseline model")

    if run:
        model_df = df_f.dropna(subset=features + [COL["risk"]]).copy()
        if len(model_df) < 5:
            st.error("Not enough rows after filtering to train a model.")
        else:
            X = model_df[features].to_numpy()
            y = model_df[COL["risk"]].to_numpy()

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.25, random_state=42
            )

            model = LinearRegression()
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            r2 = r2_score(y_test, y_pred)
            rmse = mean_squared_error(y_test, y_pred, squared=False)

            c1, c2 = st.columns(2)
            c1.metric("R² (test)", f"{r2:.3f}")
            c2.metric("RMSE (test)", f"{rmse:.3f}")

            st.caption("Use this as a prototype only — low scores mean key explanatory factors are missing.")

# -----------------------------
# Tab 5: Data Quality & Transparency
# -----------------------------
with tabs[4]:
    st.subheader("Data Quality & Transparency")

    st.markdown("### Deduplication")
    st.write(
        f"Duplicates can occur when multiple postings map to the same role during merging. "
        f"Rows were deduplicated using **{COL['link']}** (unique job links)."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows before dedupe", f"{n_before:,}")
    c2.metric("Rows after dedupe", f"{n_after:,}")
    c3.metric("Duplicates removed", f"{n_removed:,}")

    st.markdown("### H2 grouping logic")
    st.write(
        "Tech+Domain vs Tech-only is inferred from **domain_level**:\n"
        "- numeric domain_level: > 0 => Tech+Domain, else Tech-only\n"
        "- text domain_level: tokens like 'none', 'low', '0' => Tech-only; otherwise Tech+Domain"
    )

    st.markdown("### Missingness (after dedupe)")
    miss = (df.isna().mean().sort_values(ascending=False) * 100).round(1).reset_index()
    miss.columns = ["column", "missing_%"]
    st.dataframe(miss, use_container_width=True, height=360)

    st.markdown("### Preview (filtered)")
    show_cols = [COL["title"], COL["role"], "h2_group", COL["risk"], COL["growth"], COL["human"], COL["repeat"], COL["ai"], COL["link"]]
    st.dataframe(df_f[show_cols].head(50), use_container_width=True)