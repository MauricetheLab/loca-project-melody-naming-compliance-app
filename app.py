import streamlit as st
import pandas as pd
import numpy as np
import difflib
import io
import os
import re
import zipfile
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Naming Compliance — Labelium",
    page_icon="✅",
    layout="wide",
)

# ── Branding / CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.block-container { padding-top: 2rem; }

.hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f4c81 100%);
    border-radius: 16px;
    padding: 2.5rem 2.5rem 2rem;
    margin-bottom: 2rem;
    color: white;
}
.hero h1 { font-size: 2rem; font-weight: 700; margin: 0 0 .4rem; }
.hero p  { font-size: 1rem; opacity: .75; margin: 0; }

.metric-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.metric-card .value { font-size: 2rem; font-weight: 700; color: #0f172a; }
.metric-card .label { font-size: .8rem; color: #64748b; text-transform: uppercase;
                      letter-spacing: .05em; margin-top: .25rem; }

.badge-perfect   { background:#dcfce7; color:#166534; border-radius:6px;
                   padding:2px 10px; font-size:.8rem; font-weight:600; }
.badge-minor     { background:#fef9c3; color:#854d0e; border-radius:6px;
                   padding:2px 10px; font-size:.8rem; font-weight:600; }
.badge-moderate  { background:#ffedd5; color:#9a3412; border-radius:6px;
                   padding:2px 10px; font-size:.8rem; font-weight:600; }
.badge-noncompliant { background:#fee2e2; color:#991b1b; border-radius:6px;
                      padding:2px 10px; font-size:.8rem; font-weight:600; }

.stDataFrame { border-radius: 10px; overflow: hidden; }

footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Core logic (Labelium only) ─────────────────────────────────────────────────

TARGET_AGENCY = "Labelium"
AGENCY_CODE   = "c5"

def clean_val(text):
    if pd.isna(text) or str(text).strip() == "":
        return ""
    return str(text).replace("_", "-").strip().lower()


def build_compliance_report(df: pd.DataFrame) -> pd.DataFrame:
    # Filter to Labelium only
    df = df[df["Agency"].str.strip() == TARGET_AGENCY].copy()
    if df.empty:
        st.error("No rows found for Labelium in this file. Please check the Agency column.")
        st.stop()

    df["Start Date"] = pd.to_datetime(df["Start Date"])
    df["End Date"]   = pd.to_datetime(df["End Date"])

    check_cols = {
        "Division": "Division", "Signature": "Signature",
        "Axis": "Axis", "Franchise": "Franchise", "Agency": "Agency",
    }

    def diagnostic_check(group):
        issues = []
        for label, col in check_cols.items():
            if group[col].nunique() > 1:
                issues.append(f"Mixed-{label}")
        has_customer = group["Customer"].dropna().size > 0
        funnels = set(str(f).lower() for f in group["Media Funnel"].dropna())
        if any("transactional" in f for f in funnels) and not has_customer:
            issues.append("Missing-Customer-For-Transactional")
        return "Valid" if not issues else f"Inconsistent: [{', '.join(issues)}]"

    plan_diagnostics = (
        df.groupby("Plan")
        .apply(diagnostic_check, include_groups=False)
        .reset_index(name="Data Integrity Flag")
    )

    plan_stats = df.groupby("Plan").agg(
        plan_start        = ("Start Date",    "min"),
        plan_end          = ("End Date",      "max"),
        div               = ("Division",      "first"),
        sig               = ("Signature",     "first"),
        axs               = ("Axis",          "first"),
        fra               = ("Franchise",     "first"),
        age               = ("Agency",        "first"),
        po                = ("Purchase Order #", "first"),
        all_funnels       = ("Media Funnel",  lambda x: set(str(i).lower() for i in x if pd.notna(i))),
        unique_media_types= ("Media type",    lambda x: sorted([clean_val(i) for i in x if pd.notna(i) and clean_val(i)])),
        unique_customers  = ("Customer",      lambda x: sorted([clean_val(i) for i in x if pd.notna(i) and clean_val(i)])),
    ).reset_index()

    plan_stats["is_alwayson"] = (
        (plan_stats["plan_end"] - plan_stats["plan_start"]).dt.days.between(180, 366)
    )

    def format_media_types(types_list):
        unique = list(dict.fromkeys(types_list))
        if len(unique) > 3:
            return "[multiple-media-types]"
        return f"[{'-'.join(unique)}]" if unique else "[unknown-media]"

    plan_stats["m_type_str"] = plan_stats["unique_media_types"].apply(format_media_types)

    def generate_name(row):
        d = clean_val(row["div"])
        s = clean_val(row["sig"])
        a = clean_val(row["axs"])
        f = clean_val(row["fra"])
        m = row["m_type_str"]
        funnels   = row["all_funnels"]
        has_aw    = any("awareness" in fn for fn in funnels)
        has_tr    = any("transactional" in fn for fn in funnels)
        cust_list = row["unique_customers"]
        c_str     = f"[{'-'.join(cust_list)}]" if cust_list else "[no-customer]"

        if has_aw and has_tr:
            funnel_part = f"aw&tr-{c_str}"
        elif has_tr:
            funnel_part = f"tr-{c_str}"
        elif has_aw:
            funnel_part = "aw"
        else:
            funnel_part = clean_val(list(funnels)[0]) if funnels else "unknown"

        dt = "alwayson" if row["is_alwayson"] else row["plan_start"].strftime("%Y%m%d")
        p  = clean_val(row["po"]) if row["po"] != "" else "x"

        return f"{d}_{s}_{a}_{f}_{m}_{funnel_part}_{dt}_{AGENCY_CODE}_{p}"

    plan_stats["Output Plan Name"] = plan_stats.apply(generate_name, axis=1)

    final = plan_diagnostics.merge(
        plan_stats[["Plan", "div", "sig", "age", "Output Plan Name"]],
        on="Plan",
    )
    final.rename(columns={
        "Plan": "Source Plan Name",
        "div":  "Division",
        "sig":  "Signature",
        "age":  "Agency",
    }, inplace=True)
    final["Agency"] = final["Agency"].fillna("Unknown Agency")

    def similarity(row):
        src = str(row["Source Plan Name"]).strip().lower()
        gen = str(row["Output Plan Name"]).strip().lower()
        if src.startswith(gen):
            return 100.0
        return round(difflib.SequenceMatcher(None, src, gen).ratio() * 100, 2)

    final["Similarity Score (%)"] = final.apply(similarity, axis=1)

    def compliance_rating(score):
        if score == 100:  return "Perfect Match"
        if score >= 85:   return "Minor Deviations"
        if score >= 60:   return "Moderate Deviations"
        return "Non-Compliant"

    final["Compliance Rating"] = final["Similarity Score (%)"].apply(compliance_rating)

    def missing_elements(row):
        if row["Similarity Score (%)"] == 100:
            return "None"
        src  = re.sub(r"[\-_\[\] ]", "", str(row["Source Plan Name"]).lower())
        gen_parts = str(row["Output Plan Name"]).lower().split("_")
        labels = ["Division","Signature","Axis","Franchise","Media","Funnel","Date","Agency","PO Number"]
        missing = []
        for label, comp in zip(labels, gen_parts):
            if comp in ["x","other","unknown","[unknown-media]","[no-customer]"]:
                continue
            flat = re.sub(r"[\-&\[\]]", "", comp)
            if flat not in src:
                missing.append(label)
        return ", ".join(missing) if missing else "Formatting/Ordering issues only"

    final["Missing Naming Components"] = final.apply(missing_elements, axis=1)

    return final[[
        "Agency", "Division", "Signature",
        "Source Plan Name", "Output Plan Name",
        "Similarity Score (%)", "Compliance Rating",
        "Missing Naming Components", "Data Integrity Flag",
    ]]


# ── Chart helpers ──────────────────────────────────────────────────────────────

PALETTE = {
    "Perfect Match":       "#22c55e",
    "Minor Deviations":    "#eab308",
    "Moderate Deviations": "#f97316",
    "Non-Compliant":       "#ef4444",
}

def score_color(val):
    if val == 100:  return "#22c55e"
    if val >= 85:   return "#eab308"
    if val >= 60:   return "#f97316"
    return "#ef4444"


def make_bar_chart(data: pd.DataFrame, group_col: str, title: str):
    agg = (
        data.groupby(group_col)["Similarity Score (%)"]
        .mean().round(1).sort_values(ascending=True).reset_index()
    )
    if agg.empty:
        return None
    colors = [score_color(v) for v in agg["Similarity Score (%)"]]
    fig, ax = plt.subplots(figsize=(7, max(2.5, len(agg) * 0.65)))
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    bars = ax.barh(agg[group_col], agg["Similarity Score (%)"], color=colors,
                   height=0.55, edgecolor="white", linewidth=0.5)
    ax.set_xlim(0, 118)
    ax.set_xlabel("Avg Score (%)", fontsize=9, color="#64748b")
    ax.set_title(title, fontsize=11, fontweight="bold", color="#0f172a", pad=10)
    ax.tick_params(axis="y", labelsize=9, labelcolor="#334155")
    ax.tick_params(axis="x", labelsize=8, labelcolor="#94a3b8")
    sns.despine(ax=ax, left=False, bottom=True)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#cbd5e1")
    ax.set_axisbelow(True)
    for bar, val in zip(bars, agg["Similarity Score (%)"]):
        ax.text(val + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=9,
                fontweight="bold", color="#0f172a")
    plt.tight_layout()
    return fig


def make_donut(data: pd.DataFrame):
    counts = data["Compliance Rating"].value_counts()
    order  = ["Perfect Match","Minor Deviations","Moderate Deviations","Non-Compliant"]
    vals   = [counts.get(k, 0) for k in order]
    colors = [PALETTE[k] for k in order]
    fig, ax = plt.subplots(figsize=(4, 4))
    fig.patch.set_facecolor("#f8fafc")
    wedges, _ = ax.pie(
        vals, colors=colors, startangle=90,
        wedgeprops=dict(width=0.52, edgecolor="white", linewidth=2),
    )
    total = sum(vals)
    pct   = round(counts.get("Perfect Match", 0) / total * 100) if total else 0
    ax.text(0, 0, f"{pct}%\nPerfect", ha="center", va="center",
            fontsize=14, fontweight="bold", color="#0f172a")
    ax.set_title("Compliance Breakdown", fontsize=11, fontweight="bold",
                 color="#0f172a", pad=8)
    plt.tight_layout()
    return fig


# ── Excel export ───────────────────────────────────────────────────────────────

def build_excel(df: pd.DataFrame, chart_fig) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Formats
        hdr_fmt  = wb.add_format({"bold": True, "bg_color": "#D9E1F2",
                                   "border": 1, "font_name": "Arial", "font_size": 10})
        cell_fmt = wb.add_format({"font_name": "Arial", "font_size": 10, "border": 1})
        pct_fmt  = wb.add_format({"font_name": "Arial", "font_size": 10, "border": 1,
                                   "num_format": "0.00"})
        green_fmt= wb.add_format({"font_name": "Arial", "font_size": 10, "border": 1,
                                   "bg_color": "#dcfce7", "font_color": "#166534"})
        yellow_fmt=wb.add_format({"font_name": "Arial", "font_size": 10, "border": 1,
                                   "bg_color": "#fef9c3", "font_color": "#854d0e"})
        orange_fmt=wb.add_format({"font_name": "Arial", "font_size": 10, "border": 1,
                                   "bg_color": "#ffedd5", "font_color": "#9a3412"})
        red_fmt  = wb.add_format({"font_name": "Arial", "font_size": 10, "border": 1,
                                   "bg_color": "#fee2e2", "font_color": "#991b1b"})

        rating_fmt = {
            "Perfect Match":       green_fmt,
            "Minor Deviations":    yellow_fmt,
            "Moderate Deviations": orange_fmt,
            "Non-Compliant":       red_fmt,
        }

        # ── Sheet 1: Dashboard image
        ws_dash = wb.add_worksheet("Dashboard")
        ws_dash.hide_gridlines(2)
        ws_dash.write("B2", "Labelium — Naming Compliance Report",
                      wb.add_format({"bold": True, "font_size": 16, "font_name": "Arial",
                                     "font_color": "#0f172a"}))
        ws_dash.write("B3", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                      wb.add_format({"font_size": 10, "font_name": "Arial",
                                     "font_color": "#64748b"}))
        img_buf = io.BytesIO()
        chart_fig.savefig(img_buf, format="png", bbox_inches="tight", dpi=130)
        img_buf.seek(0)
        ws_dash.insert_image("B5", "", {"image_data": img_buf,
                                         "x_scale": 0.85, "y_scale": 0.85})

        # ── Sheet 2: Data
        df.to_excel(writer, sheet_name="Compliance Data", index=False)
        ws = writer.sheets["Compliance Data"]
        ws.hide_gridlines(2)
        col_widths = [14, 12, 18, 52, 52, 14, 20, 32, 32]
        for i, (col, width) in enumerate(zip(df.columns, col_widths)):
            ws.write(0, i, col, hdr_fmt)
            ws.set_column(i, i, width)

        for row_idx, row in df.iterrows():
            excel_row = row_idx + 1
            for col_idx, (col, val) in enumerate(row.items()):
                if col == "Compliance Rating":
                    fmt = rating_fmt.get(str(val), cell_fmt)
                elif col == "Similarity Score (%)":
                    fmt = pct_fmt
                else:
                    fmt = cell_fmt
                ws.write(excel_row, col_idx, val if pd.notna(val) else "", fmt)

        # ── Sheet 3: Summary stats
        ws_sum = wb.add_worksheet("Summary")
        ws_sum.hide_gridlines(2)
        title_fmt = wb.add_format({"bold": True, "font_size": 13, "font_name": "Arial",
                                    "font_color": "#0f172a"})
        ws_sum.write("B2", "Summary Statistics", title_fmt)
        stats = df["Compliance Rating"].value_counts().reset_index()
        stats.columns = ["Rating", "Count"]
        stats["% of Total"] = (stats["Count"] / len(df) * 100).round(1)
        ws_sum.write_row("B4", ["Rating", "Count", "% of Total"], hdr_fmt)
        for i, row in stats.iterrows():
            fmt = rating_fmt.get(str(row["Rating"]), cell_fmt)
            ws_sum.write(4 + i, 1, row["Rating"],    fmt)
            ws_sum.write(4 + i, 2, row["Count"],     cell_fmt)
            ws_sum.write(4 + i, 3, row["% of Total"], pct_fmt)
        ws_sum.set_column("B:B", 22)
        ws_sum.set_column("C:C", 10)
        ws_sum.set_column("D:D", 12)

    buf.seek(0)
    return buf.read()


# ── UI ─────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
  <h1>🎯 Naming Compliance Checker</h1>
  <p>Labelium · L'Oréal Canada · Powered by Cosmo5</p>
</div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Drop your Melody forecast export here (.xlsx or .csv)",
    type=["xlsx", "csv"],
    help="Export from Melody, delete costing columns, then upload here.",
)

if uploaded is None:
    st.info("👆 Upload a file above to get started.")
    st.markdown("""
    **How to use this tool:**
    1. Export your forecast from Melody
    2. Delete the costing details columns
    3. Upload the file above
    4. Review the compliance dashboard
    5. Download the Excel report
    """)
    st.stop()

# ── Load & process ─────────────────────────────────────────────────────────────
with st.spinner("Analysing naming compliance…"):
    try:
        raw = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
               else pd.read_excel(uploaded))
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    result = build_compliance_report(raw)

# ── KPI row ────────────────────────────────────────────────────────────────────
total        = len(result)
perfect      = (result["Compliance Rating"] == "Perfect Match").sum()
minor        = (result["Compliance Rating"] == "Minor Deviations").sum()
moderate     = (result["Compliance Rating"] == "Moderate Deviations").sum()
non_compliant= (result["Compliance Rating"] == "Non-Compliant").sum()
avg_score    = result["Similarity Score (%)"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
for col, val, label in [
    (c1, total,         "Total Plans"),
    (c2, f"{avg_score:.1f}%", "Avg Score"),
    (c3, perfect,       "✅ Perfect"),
    (c4, minor + moderate, "⚠️ Deviations"),
    (c5, non_compliant, "❌ Non-Compliant"),
]:
    col.markdown(f"""
    <div class="metric-card">
      <div class="value">{val}</div>
      <div class="label">{label}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Charts ─────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1])

with col_left:
    div_fig = make_bar_chart(result, "Division", "Score by Division")
    if div_fig:
        st.pyplot(div_fig, use_container_width=True)
        plt.close(div_fig)

with col_right:
    donut_fig = make_donut(result)
    st.pyplot(donut_fig, use_container_width=True)
    plt.close(donut_fig)

sig_fig = make_bar_chart(result, "Signature", "Score by Signature")
if sig_fig:
    st.pyplot(sig_fig, use_container_width=True)
    plt.close(sig_fig)

# ── Filters + table ────────────────────────────────────────────────────────────
st.markdown("### 📋 Plan-Level Results")

filter_col1, filter_col2, filter_col3 = st.columns(3)
with filter_col1:
    div_filter = st.multiselect("Division", sorted(result["Division"].dropna().unique()))
with filter_col2:
    rating_filter = st.multiselect("Compliance Rating", result["Compliance Rating"].unique())
with filter_col3:
    score_min = st.slider("Min Score (%)", 0, 100, 0)

filtered = result.copy()
if div_filter:
    filtered = filtered[filtered["Division"].isin(div_filter)]
if rating_filter:
    filtered = filtered[filtered["Compliance Rating"].isin(rating_filter)]
filtered = filtered[filtered["Similarity Score (%)"] >= score_min]

def color_rating(val):
    colors = {
        "Perfect Match":       "background-color:#dcfce7; color:#166534",
        "Minor Deviations":    "background-color:#fef9c3; color:#854d0e",
        "Moderate Deviations": "background-color:#ffedd5; color:#9a3412",
        "Non-Compliant":       "background-color:#fee2e2; color:#991b1b",
    }
    return colors.get(val, "")

st.dataframe(
    filtered.style.applymap(color_rating, subset=["Compliance Rating"])
                  .format({"Similarity Score (%)": "{:.1f}%"}),
    use_container_width=True,
    height=420,
)

st.caption(f"Showing {len(filtered)} of {total} plans")

# ── Export ─────────────────────────────────────────────────────────────────────
st.markdown("### 📥 Download Report")

# Build a combined chart for the Excel export
combined_fig, axes = plt.subplots(1, 3, figsize=(22, 7))
combined_fig.patch.set_facecolor("#f8fafc")
combined_fig.suptitle("Labelium — Naming Compliance Dashboard",
                       fontsize=18, fontweight="bold", color="#0f172a", y=1.02)

for ax, col, title in [
    (axes[0], "Division",  "Score by Division"),
    (axes[1], "Signature", "Score by Signature"),
    (axes[2], None,        None),
]:
    if col:
        agg = (result.groupby(col)["Similarity Score (%)"]
               .mean().round(1).sort_values(ascending=True).reset_index())
        colors = [score_color(v) for v in agg["Similarity Score (%)"]]
        ax.barh(agg[col], agg["Similarity Score (%)"], color=colors,
                height=0.55, edgecolor="white")
        ax.set_xlim(0, 118)
        ax.set_title(title, fontsize=12, fontweight="bold", color="#0f172a")
        ax.set_facecolor("#f8fafc")
        sns.despine(ax=ax, left=False, bottom=True)
        ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#cbd5e1")
        for i, (_, row) in enumerate(agg.iterrows()):
            ax.text(row["Similarity Score (%)"] + 1.5, i,
                    f"{row['Similarity Score (%)']:.1f}%",
                    va="center", fontsize=9, fontweight="bold", color="#0f172a")

# Donut in 3rd panel
counts = result["Compliance Rating"].value_counts()
order  = ["Perfect Match","Minor Deviations","Moderate Deviations","Non-Compliant"]
vals   = [counts.get(k, 0) for k in order]
colors = [PALETTE[k] for k in order]
axes[2].pie(vals, colors=colors, startangle=90,
            wedgeprops=dict(width=0.52, edgecolor="white", linewidth=2))
total_plans = sum(vals)
pct_perfect = round(counts.get("Perfect Match", 0) / total_plans * 100) if total_plans else 0
axes[2].text(0, 0, f"{pct_perfect}%\nPerfect", ha="center", va="center",
             fontsize=14, fontweight="bold", color="#0f172a")
axes[2].set_title("Compliance Breakdown", fontsize=12, fontweight="bold", color="#0f172a")
axes[2].set_facecolor("#f8fafc")

legend_patches = [mpatches.Patch(color=PALETTE[k], label=k) for k in order]
combined_fig.legend(handles=legend_patches, loc="lower center", ncol=4,
                    bbox_to_anchor=(0.5, -0.04), frameon=False, fontsize=11)
combined_fig.tight_layout()

excel_bytes = build_excel(result, combined_fig)
plt.close(combined_fig)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
st.download_button(
    label="⬇️ Download Labelium Report (.xlsx)",
    data=excel_bytes,
    file_name=f"Labelium_Naming_Compliance_{timestamp}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
