import streamlit as st
import pandas as pd
import difflib
import io
import re
import base64
import pathlib
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

# ── Page config ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Naming Compliance — Labelium x L'Oreal",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Logo ─────────────────────────────────────────────────────────────────────────
LOGO_PATH = pathlib.Path(__file__).parent / "loreal_logo.jpg"
if LOGO_PATH.exists():
    with open(LOGO_PATH, "rb") as f:
        LOGO_B64 = base64.b64encode(f.read()).decode()
    LOGO_SRC = f"data:image/jpeg;base64,{LOGO_B64}"
else:
    LOGO_SRC = ""

# ── CSS ──────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans', sans-serif; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

.hero {
    background: linear-gradient(135deg, #121212 0%, #172D9D 60%, #040FDA 100%);
    border-radius: 16px; padding: 2rem 2.5rem; margin-bottom: 1.5rem;
    display: flex; align-items: center; justify-content: space-between; gap: 2rem;
}
.hero-text h1 { font-size: 1.8rem; font-weight: 700; color: #FFFFFF; margin: 0 0 .3rem; }
.hero-text p  { font-size: .95rem; color: #00E2E0; margin: 0; }
.hero-logo img { height: 52px; object-fit: contain; filter: brightness(0) invert(1); }

.kpi-card {
    background: #FFFFFF; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 1.1rem 1.2rem; text-align: center;
    box-shadow: 0 1px 4px rgba(4,15,218,.07); border-top: 3px solid #040FDA;
}
.kpi-card .value { font-size: 1.9rem; font-weight: 700; color: #121212; }
.kpi-card .label { font-size: .72rem; color: #64748b; text-transform: uppercase;
                   letter-spacing: .06em; margin-top: .2rem; font-weight: 700; }
.kpi-card.green  { border-top-color: #22c55e; }
.kpi-card.yellow { border-top-color: #eab308; }
.kpi-card.red    { border-top-color: #ef4444; }

.section-title {
    font-size: .9rem; font-weight: 700; color: #121212;
    text-transform: uppercase; letter-spacing: .07em;
    margin: 1.5rem 0 .75rem; padding-left: .75rem;
    border-left: 3px solid #040FDA;
}
.sidebar-step {
    background: #f8fafc; border-radius: 10px; padding: .65rem .9rem;
    margin-bottom: .5rem; border-left: 3px solid #040FDA;
    font-size: .85rem; color: #1e293b; line-height: 1.5;
}
.sidebar-step strong { color: #040FDA; display: block; }

/* Make the Streamlit file uploader bigger */
[data-testid="stFileUploader"] {
    padding: 1.5rem;
    border-radius: 12px;
    border: 2px dashed #040FDA !important;
    background: linear-gradient(135deg, rgba(4,15,218,.04), rgba(0,226,224,.04));
}
[data-testid="stFileUploader"] label {
    font-size: 1rem !important;
    font-weight: 700 !important;
    color: #040FDA !important;
}
[data-testid="stFileUploaderDropzone"] {
    min-height: 120px !important;
}

footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    if LOGO_SRC:
        st.markdown(
            f'<div style="text-align:center;padding:1rem 0 1.2rem;">'
            f'<img src="{LOGO_SRC}" style="height:40px;object-fit:contain;filter:brightness(0);"/>'
            f'<div style="margin-top:.5rem;font-size:.72rem;color:#64748b;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.06em;">Naming Compliance Tool</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### How to export from Melody")
    for title, desc in [
        ("Step 1", "Log into Melody and navigate to your campaign forecast"),
        ("Step 2", "Select the date range and all Labelium plans"),
        ("Step 3", "Click Export and choose Excel (.xlsx) format"),
        ("Step 4", "Open the file and delete all costing / budget columns"),
        ("Step 5", "Save the file and upload it in the main panel"),
    ]:
        st.markdown(
            f'<div class="sidebar-step"><strong>{title}</strong>{desc}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        '<div style="font-size:.78rem;color:#94a3b8;text-align:center;line-height:1.5;">'
        'Powered by <strong style="color:#040FDA;">Cosmo5</strong><br>'
        'Questions? Contact the data team</div>',
        unsafe_allow_html=True,
    )

# ── Hero ─────────────────────────────────────────────────────────────────────────
logo_tag = f'<div class="hero-logo"><img src="{LOGO_SRC}" /></div>' if LOGO_SRC else ""
st.markdown(
    f'<div class="hero">'
    f'<div class="hero-text"><h1>Naming Compliance Checker</h1>'
    f"<p>Labelium x L'Oreal Canada &nbsp;·&nbsp; Powered by Cosmo5</p></div>"
    f"{logo_tag}</div>",
    unsafe_allow_html=True,
)

# ── Constants ────────────────────────────────────────────────────────────────────
TARGET_AGENCY = "Labelium"
AGENCY_CODE   = "c5"

AGENCY_MAP = {
    "Labelium":      "c5",
    "CJ":            "cj",
    "Media Experts": "mex",
    "Wavemaker":     "wm",
}

PALETTE = {
    "Perfect Match":       "#22c55e",
    "Minor Deviations":    "#eab308",
    "Moderate Deviations": "#f97316",
    "Non-Compliant":       "#ef4444",
}

# ── Core helpers ─────────────────────────────────────────────────────────────────
def clean_val(text):
    if pd.isna(text) or str(text).strip() == "":
        return ""
    return str(text).replace("_", "-").strip().lower()


def build_report(df: pd.DataFrame) -> pd.DataFrame:
    # Keep all agencies but tag them
    df = df.copy()
    df["Start Date"] = pd.to_datetime(df["Start Date"])
    df["End Date"]   = pd.to_datetime(df["End Date"])

    def diag(group):
        issues = []
        for col in ["Division", "Signature", "Axis", "Franchise", "Agency"]:
            if group[col].nunique() > 1:
                issues.append(f"Mixed-{col}")
        funnels = set(str(f).lower() for f in group["Media Funnel"].dropna())
        if any("transactional" in f for f in funnels) and group["Customer"].dropna().size == 0:
            issues.append("Missing-Customer-For-Transactional")
        return "Valid" if not issues else f"Inconsistent: [{', '.join(issues)}]"

    diag_df = (
        df.groupby("Plan")
        .apply(diag, include_groups=False)
        .reset_index(name="Data Integrity Flag")
    )

    stats = df.groupby("Plan").agg(
        plan_start         = ("Start Date",       "min"),
        plan_end           = ("End Date",         "max"),
        div                = ("Division",         "first"),
        sig                = ("Signature",        "first"),
        axs                = ("Axis",             "first"),
        fra                = ("Franchise",        "first"),
        age                = ("Agency",           "first"),
        po                 = ("Purchase Order #", "first"),
        all_funnels        = ("Media Funnel",     lambda x: set(str(i).lower() for i in x if pd.notna(i))),
        unique_media_types = ("Media type",       lambda x: sorted([clean_val(i) for i in x if pd.notna(i) and clean_val(i)])),
        unique_customers   = ("Customer",         lambda x: sorted(list(set([clean_val(i) for i in x if pd.notna(i) and clean_val(i)])))),
    ).reset_index()

    stats["is_alwayson"] = (stats["plan_end"] - stats["plan_start"]).dt.days.between(180, 366)

    def fmt_media(t):
        u = list(dict.fromkeys(t))
        return "[multiple-media-types]" if len(u) >= 4 else (f"[{'-'.join(u)}]" if u else "[unknown-media]")

    stats["m_type_str"] = stats["unique_media_types"].apply(fmt_media)

    def gen_name(row):
        d, s, a, f = (clean_val(row["div"]), clean_val(row["sig"]),
                      clean_val(row["axs"]), clean_val(row["fra"]))
        m, funnels, cust = row["m_type_str"], row["all_funnels"], row["unique_customers"]
        has_aw = any("awareness" in fn for fn in funnels)
        has_tr = any("transactional" in fn for fn in funnels)
        c_str  = f"[{'-'.join(cust)}]" if cust else "[no-customer]"
        fp = (f"aw&tr-{c_str}" if has_aw and has_tr
              else f"tr-{c_str}" if has_tr
              else "aw" if has_aw
              else (clean_val(list(funnels)[0]) if funnels else "unknown"))
        dt  = "alwayson" if row["is_alwayson"] else row["plan_start"].strftime("%Y%m%d")
        ap  = AGENCY_MAP.get(str(row["age"]), "other").lower()
        p   = clean_val(row["po"]) if row["po"] != "" else "x"
        return f"{d}_{s}_{a}_{f}_{m}_{fp}_{dt}_{ap}_{p}"

    stats["Output Plan Name"] = stats.apply(gen_name, axis=1)

    final = diag_df.merge(stats[["Plan", "div", "sig", "age", "Output Plan Name"]], on="Plan")
    final.rename(columns={
        "Plan": "Source Plan Name", "div": "Division",
        "sig": "Signature",         "age": "Agency",
    }, inplace=True)
    final["Agency"] = final["Agency"].fillna("Unknown")

    def sim(row):
        s = str(row["Source Plan Name"]).strip().lower()
        g = str(row["Output Plan Name"]).strip().lower()
        return 100.0 if s.startswith(g) else round(difflib.SequenceMatcher(None, s, g).ratio() * 100, 2)

    final["Similarity Score (%)"] = final.apply(sim, axis=1)
    final["Compliance Rating"] = final["Similarity Score (%)"].apply(
        lambda v: "Perfect Match" if v == 100
        else "Minor Deviations" if v >= 85
        else "Moderate Deviations" if v >= 60
        else "Non-Compliant"
    )

    def missing(row):
        if row["Similarity Score (%)"] == 100:
            return "None"
        src = re.sub(r"[\-_\[\] ]", "", str(row["Source Plan Name"]).lower())
        labels = ["Division","Signature","Axis","Franchise","Media","Funnel","Date","Agency","PO Number"]
        miss = []
        for label, comp in zip(labels, str(row["Output Plan Name"]).lower().split("_")):
            if comp in ["x","other","unknown","[unknown-media]","[no-customer]"]:
                continue
            if re.sub(r"[\-&\[\]]", "", comp) not in src:
                miss.append(label)
        return ", ".join(miss) if miss else "Formatting/Ordering issues only"

    final["Missing Naming Components"] = final.apply(missing, axis=1)

    return final[[
        "Agency", "Division", "Signature",
        "Source Plan Name", "Output Plan Name",
        "Similarity Score (%)", "Compliance Rating",
        "Missing Naming Components", "Data Integrity Flag",
    ]]


def score_color(v):
    return "#22c55e" if v == 100 else "#eab308" if v >= 85 else "#f97316" if v >= 60 else "#ef4444"


def make_bar(data, col, title):
    agg = data.groupby(col)["Similarity Score (%)"].mean().round(1).sort_values(ascending=True).reset_index()
    if agg.empty:
        return None
    fig, ax = plt.subplots(figsize=(7, max(2.5, len(agg) * .65)))
    fig.patch.set_facecolor("#f8fafc"); ax.set_facecolor("#f8fafc")
    bars = ax.barh(agg[col], agg["Similarity Score (%)"],
                   color=[score_color(v) for v in agg["Similarity Score (%)"]],
                   height=.55, edgecolor="white")
    ax.set_xlim(0, 118)
    ax.set_title(title, fontsize=11, fontweight="bold", color="#121212", pad=10)
    ax.tick_params(axis="y", labelsize=9, labelcolor="#334155")
    ax.tick_params(axis="x", labelsize=8, labelcolor="#94a3b8")
    sns.despine(ax=ax, left=False, bottom=True)
    ax.xaxis.grid(True, linestyle="--", alpha=.5, color="#cbd5e1"); ax.set_axisbelow(True)
    for bar, val in zip(bars, agg["Similarity Score (%)"]):
        ax.text(val + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=9, fontweight="bold", color="#121212")
    plt.tight_layout()
    return fig


def make_donut(data):
    counts = data["Compliance Rating"].value_counts()
    order  = list(PALETTE.keys())
    vals   = [counts.get(k, 0) for k in order]
    fig, ax = plt.subplots(figsize=(4, 4))
    fig.patch.set_facecolor("#f8fafc"); ax.set_facecolor("#f8fafc")
    ax.pie(vals, colors=[PALETTE[k] for k in order], startangle=90,
           wedgeprops=dict(width=.52, edgecolor="white", linewidth=2))
    total = sum(vals)
    pct = round(counts.get("Perfect Match", 0) / total * 100) if total else 0
    ax.text(0, 0, f"{pct}%\nPerfect", ha="center", va="center",
            fontsize=14, fontweight="bold", color="#121212")
    ax.set_title("Compliance Breakdown", fontsize=11, fontweight="bold", color="#121212", pad=8)
    plt.tight_layout()
    return fig


# ── Upload ───────────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload your Melody Forecast Export (.xlsx or .csv) — delete costing columns first",
    type=["xlsx", "csv"],
)

if uploaded is None:
    st.info("Upload a Melody export above to generate the compliance report.")
    st.stop()

# ── Process ──────────────────────────────────────────────────────────────────────
with st.spinner("Analysing naming compliance…"):
    try:
        raw = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Could not read file: {e}"); st.stop()
    result = build_report(raw)

# ── Filters ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Filters</div>', unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    agency_f  = st.multiselect("Agency", sorted(result["Agency"].dropna().unique()))
with fc2:
    div_f     = st.multiselect("Division", sorted(result["Division"].dropna().unique()))
with fc3:
    sig_f     = st.multiselect("Signature / Brand", sorted(result["Signature"].dropna().unique()))
with fc4:
    rating_f  = st.multiselect("Compliance Rating", list(PALETTE.keys()))

filtered = result.copy()
if agency_f:  filtered = filtered[filtered["Agency"].isin(agency_f)]
if div_f:     filtered = filtered[filtered["Division"].isin(div_f)]
if sig_f:     filtered = filtered[filtered["Signature"].isin(sig_f)]
if rating_f:  filtered = filtered[filtered["Compliance Rating"].isin(rating_f)]

# ── KPIs ─────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Key Metrics</div>', unsafe_allow_html=True)
total    = len(filtered)
perfect  = (filtered["Compliance Rating"] == "Perfect Match").sum()
minor    = (filtered["Compliance Rating"] == "Minor Deviations").sum()
moderate = (filtered["Compliance Rating"] == "Moderate Deviations").sum()
nc       = (filtered["Compliance Rating"] == "Non-Compliant").sum()
avg      = filtered["Similarity Score (%)"].mean() if total else 0

for col, val, label, cls in zip(
    st.columns(5),
    [total, f"{avg:.1f}%", perfect, minor + moderate, nc],
    ["Total Plans", "Avg Score", "Perfect", "Deviations", "Non-Compliant"],
    ["", "", "green", "yellow", "red"],
):
    col.markdown(
        f'<div class="kpi-card {cls}"><div class="value">{val}</div>'
        f'<div class="label">{label}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Charts ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Performance Charts</div>', unsafe_allow_html=True)
cl, cr = st.columns(2)
with cl:
    fig = make_bar(filtered, "Division", "Score by Division")
    if fig:
        st.pyplot(fig, use_container_width=True); plt.close(fig)
with cr:
    d = make_donut(filtered)
    st.pyplot(d, use_container_width=True); plt.close(d)

# ── Table ─────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Plan-Level Results</div>', unsafe_allow_html=True)

COLOR_MAP = {
    "Perfect Match":       "background-color:#dcfce7;color:#166534",
    "Minor Deviations":    "background-color:#fef9c3;color:#854d0e",
    "Moderate Deviations": "background-color:#ffedd5;color:#9a3412",
    "Non-Compliant":       "background-color:#fee2e2;color:#991b1b",
}

# Use map() instead of deprecated applymap()
styled = (
    filtered.style
    .map(lambda v: COLOR_MAP.get(v, ""), subset=["Compliance Rating"])
    .format({"Similarity Score (%)": "{:.1f}%"})
)

st.dataframe(styled, use_container_width=True, height=420)
st.caption(f"Showing {len(filtered):,} of {len(result):,} plans")

# ── Download ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Download Report</div>', unsafe_allow_html=True)

def build_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb   = writer.book
        hdr  = wb.add_format({"bold": True, "bg_color": "#040FDA", "font_color": "#FFFFFF",
                               "border": 1, "font_name": "Noto Sans", "font_size": 10})
        cell = wb.add_format({"font_name": "Noto Sans", "font_size": 10, "border": 1})
        pct  = wb.add_format({"font_name": "Noto Sans", "font_size": 10, "border": 1, "num_format": "0.00"})
        rfmt = {
            "Perfect Match":       wb.add_format({"font_name":"Noto Sans","font_size":10,"border":1,"bg_color":"#dcfce7","font_color":"#166534"}),
            "Minor Deviations":    wb.add_format({"font_name":"Noto Sans","font_size":10,"border":1,"bg_color":"#fef9c3","font_color":"#854d0e"}),
            "Moderate Deviations": wb.add_format({"font_name":"Noto Sans","font_size":10,"border":1,"bg_color":"#ffedd5","font_color":"#9a3412"}),
            "Non-Compliant":       wb.add_format({"font_name":"Noto Sans","font_size":10,"border":1,"bg_color":"#fee2e2","font_color":"#991b1b"}),
        }

        # Sheet 1 — Full compliance data
        df.to_excel(writer, sheet_name="Compliance Data", index=False)
        ws = writer.sheets["Compliance Data"]
        ws.hide_gridlines(2)
        for i, (c, w) in enumerate(zip(df.columns, [14, 12, 20, 55, 55, 14, 22, 35, 25])):
            ws.write(0, i, c, hdr); ws.set_column(i, i, w)
        for ri, row in df.iterrows():
            for ci, (c, v) in enumerate(row.items()):
                fmt = rfmt.get(str(v), cell) if c == "Compliance Rating" else (pct if c == "Similarity Score (%)" else cell)
                ws.write(ri + 1, ci, v if pd.notna(v) else "", fmt)

        # Sheet 2 — Clean plan name comparison (Agency / Division / Brand / Old / New)
        export_cols = ["Agency", "Division", "Signature", "Source Plan Name", "Output Plan Name"]
        plan_df = df[export_cols].copy()
        plan_df.columns = ["Agency", "Division", "Brand", "Current Plan Name", "Proposed Plan Name"]
        plan_df.to_excel(writer, sheet_name="Plan Name Comparison", index=False)
        ws2 = writer.sheets["Plan Name Comparison"]
        ws2.hide_gridlines(2)
        for i, (c, w) in enumerate(zip(plan_df.columns, [14, 12, 22, 60, 60])):
            ws2.write(0, i, c, hdr); ws2.set_column(i, i, w)
        for ri, row in plan_df.iterrows():
            for ci, v in enumerate(row):
                ws2.write(ri + 1, ci, v if pd.notna(v) else "", cell)

        # Sheet 3 — Summary
        ws_s = wb.add_worksheet("Summary")
        ws_s.hide_gridlines(2)
        ws_s.write("B2", "Summary Statistics",
                   wb.add_format({"bold": True, "font_size": 13, "font_name": "Noto Sans"}))
        stats = df["Compliance Rating"].value_counts().reset_index()
        stats.columns = ["Rating", "Count"]
        stats["%"] = (stats["Count"] / len(df) * 100).round(1)
        ws_s.write_row("B4", ["Rating", "Count", "% of Total"], hdr)
        for i, row in stats.iterrows():
            ws_s.write(4+i, 1, row["Rating"], rfmt.get(row["Rating"], cell))
            ws_s.write(4+i, 2, row["Count"],  cell)
            ws_s.write(4+i, 3, row["%"],      pct)
        ws_s.set_column("B:D", 20)

    buf.seek(0)
    return buf.read()

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
st.download_button(
    label="Download Compliance Report (.xlsx)",
    data=build_excel(filtered),
    file_name=f"Labelium_Naming_Compliance_{ts}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
