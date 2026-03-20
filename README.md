
# PediaSense AI Portal

A functional Flask website for pediatric nursing education with:
- role-based login: **student**, **faculty**, **manager**
- NANDA-aligned case analyzer
- quiz mode
- faculty analytics
- manager panel for users and quiz questions
- optional OpenAI-assisted explanations
- Supabase/Postgres-ready deployment

## Demo accounts
- Student: `student@pediasense.ai` / `Student123!`
- Faculty: `faculty@pediasense.ai` / `Faculty123!`
- Manager: `manager@pediasense.ai` / `Manager123!`

## Local run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

## Render deployment
Start command:
```bash
gunicorn app:app
```

## Environment variables
Set these in Render:
- `SECRET_KEY` = your-random-secret
- `DATABASE_URL` = your Supabase Postgres connection string
- `OPENAI_API_KEY` = optional, only if you want OpenAI-assisted explanations
- `OPENAI_MODEL` = optional, default `gpt-4.1-mini`

## Supabase notes
Supabase provides the Postgres connection string in the dashboard under **Connect**. For SQLAlchemy, the connection string should use the `postgresql://` scheme. citeturn123075search1turn123075search9

## OpenAI notes
The app keeps the API key on the server side and uses the Responses API path through the Python SDK for optional explanatory text. Responses is part of the current official OpenAI API reference. citeturn123075search0

## Important design note
Diagnosis selection is intentionally based on a curated NANDA-aligned library inside the app. Optional OpenAI output is used only to enrich explanation, caregiver teaching, and safety notes.
