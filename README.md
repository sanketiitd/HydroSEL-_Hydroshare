# Hydroshare (Streamlit app)

This repository contains a Streamlit app (`app.py`) for HydroLab Portal.

## Deploy to Streamlit Cloud
1. Push this repository to GitHub.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click "New app" → select this repository and branch `main`.
4. Set the **main file** to `app.py` and click "Deploy".

## Notes
- Add any secrets (API keys, DB credentials) in Streamlit Cloud's "Settings → Secrets" — do not commit secrets to the repo.
- The local SQLite DB (`hydro_storage.db`) is ephemeral on Streamlit Cloud; consider using an external DB for persistent data.

