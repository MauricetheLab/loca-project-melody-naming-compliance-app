# 🎯 Naming Compliance Checker — Labelium / L'Oréal Canada

A Streamlit web app that audits media plan naming convention compliance for the Labelium agency reports from Melody exports.

## What it does

- Accepts a Melody forecast export (`.xlsx` or `.csv`)
- Filters to **Labelium plans only**
- Reconstructs the expected plan name from the data and compares it to the actual submitted name
- Scores each plan and flags missing naming components
- Generates an interactive dashboard with charts by Division and Signature
- Exports a formatted Excel report (Dashboard + Data + Summary tabs)

## How to use

1. Export your forecast from Melody
2. Delete the costing details columns
3. Upload the file in the app
4. Review compliance scores and filter results
5. Download the Excel report

---

## 🚀 Deploy to Streamlit Cloud (10 minutes)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_ORG/naming-compliance-app.git
git push -u origin main
```

### Step 2 — Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click **"New app"**
4. Select your repo → branch: `main` → main file: `app.py`
5. Click **Deploy**

Your app will be live at:
`https://YOUR_ORG-naming-compliance-app-app-XXXXX.streamlit.app`

Share that URL with your team — no account needed to use it.

---

## 🗂 Project Structure

```
naming-compliance-app/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Required columns in the upload

The uploaded file must contain these columns (standard Melody export):

| Column | Description |
|---|---|
| `Plan` | The plan name as submitted by the agency |
| `Agency` | Must include "Labelium" rows |
| `Division` | e.g. CPD, ACD, LLD, PPD |
| `Signature` | Brand signature |
| `Axis` | Media axis |
| `Franchise` | Product franchise |
| `Media Funnel` | Awareness or Transactional |
| `Media type` | e.g. Social Media, Online Multiformat Ads |
| `Customer` | Required for Transactional plans |
| `Purchase Order #` | PO number |
| `Start Date` | Flight start date |
| `End Date` | Flight end date |

## Compliance Scoring

| Score | Rating |
|---|---|
| 100% | ✅ Perfect Match |
| 85–99% | ⚠️ Minor Deviations |
| 60–84% | 🟠 Moderate Deviations |
| < 60% | ❌ Non-Compliant |

> **Note:** If the agency appends a valid suffix (e.g. `_BFCM`, `_v2`) to an otherwise correct name, it still scores 100%.

## Naming Convention Reference

Expected format:
```
{division}_{signature}_{axis}_{franchise}_{[media-types]}_{funnel+customer}_{date}_{agency-code}_{PO#}
```

- **date** → `alwayson` if flight is 180–366 days, otherwise `YYYYMMDD`
- **agency-code** → Labelium = `c5`
- **funnel** → `aw` (Awareness) / `tr-[customer]` (Transactional) / `aw&tr-[customer]` (both)
