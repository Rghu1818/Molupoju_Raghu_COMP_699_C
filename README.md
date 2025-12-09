# Big Data Analytics Platform (Streamlit)

A Streamlit-only, multipage Big Data Analytics platform for live data integration, processing, alerting, and interactive visualization with **AI-powered insights using Google Gemini**. Includes 9 major use cases:

1) User Authentication
2) Manage Data Sources
3) Ingestion Pipeline Monitoring
4) Processing & Anomaly Detection
5) Interactive Dashboards (Charts, Graphs, Heatmaps)
6) Real-time Alerts
7) Ad-hoc Query Execution (with Natural Language to SQL)
8) Admin & User Management
9) **🤖 AI Assistant** - Natural language queries, data insights, and intelligent analysis

## Quick Start (Windows)

1. Create and activate a virtual environment (recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Gemini AI** (optional but recommended):
   - Get a free API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Update `GEMINI_API_KEY` in `core/config.py`
   - See [GEMINI_SETUP.md](GEMINI_SETUP.md) for detailed instructions
4. Run the app:
   ```bash
   streamlit run streamlit_app.py
   ```

The app uses Streamlit's pages system. The main entry is `streamlit_app.py` and feature pages live in `pages/`.

## Project Structure

- streamlit_app.py
- core/
  - __init__.py
  - config.py
  - auth.py
  - data_sources.py
  - ingestion.py
  - processing.py
  - storage.py
  - alerts.py
  - visualization.py
- pages/
  - 1_🧭_Home.py
  - 2_🔌_Data_Sources.py
  - 3_📥_Pipelines.py
  - 4_⚙️_Processing.py
  - 5_📊_Dashboards.py
  - 6_🚨_Alerts.py
  - 7_🔎_AdHoc_Query.py
  - 8_👤_Admin.py
  - 9_📄_About.py
- data/
  - (SQLite DB and cached files created at runtime)
- requirements.txt
- README.md

## AI Features

With Gemini AI configured, you get:

- **Natural Language to SQL**: Ask questions in plain English, get SQL queries automatically
- **Anomaly Explanations**: AI explains detected anomalies and suggests causes
- **Data Insights**: Automatic pattern detection and trend analysis
- **Alert Suggestions**: AI recommends optimal alert rules for your data
- **Interactive Chat**: Chat with AI about your data and get instant answers

## Notes

- **Gemini API key recommended** for AI features. Get one free at [Google AI Studio](https://makersuite.google.com/app/apikey)
- A public endpoint (CoinGecko) is used for demo financial data; if it rate-limits, the app falls back to synthetic data.
- Data is stored in a local SQLite database under `data/platform.db`.
- Authentication is a simple local username/password demo (not production-grade).
- Alerts support webhook and SMTP notifications.

## Extending

- Replace/extend `core/data_sources.py` with real connectors.
- Enhance `core/alerts.py` with email/SMS/webhook integrations.
- Add RBAC and persisted users in `core/auth.py`.
- Scale storage (Postgres, data lake) replacing `core/storage.py` logic.
