# PediaSense AI - Web Deployment Version

This version is ready for **web deployment** and supports a **hosted PostgreSQL database**.

## What changed
- Uses **Flask + SQLAlchemy**
- Works with **hosted PostgreSQL** through `DATABASE_URL`
- Includes `render.yaml` for one-click deployment on Render
- Falls back to local SQLite only if `DATABASE_URL` is not set

## Local run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```
Open `http://127.0.0.1:5001`

## Deploy on Render with Supabase / Neon / Render Postgres
1. Push this folder to GitHub.
2. Create a hosted PostgreSQL database.
3. Copy the database connection string.
4. Create a new **Web Service** on Render from your GitHub repo.
5. Render will read `render.yaml`.
6. Set `DATABASE_URL` in Render to your hosted PostgreSQL URL.
7. Deploy.

## Suggested hosted database options
- Supabase Postgres
- Neon Postgres
- Render Postgres

## Example environment values
```env
SECRET_KEY=your-random-secret
DATABASE_URL=postgresql://username:password@host:5432/database
```

## Notes for defense
You can truthfully say:
- the system is fully web-based
- the database can be cloud-hosted
- users can access the app through a link
- student attempts persist in an online database

## Main routes
- `/` - app UI
- `/api/analyze-case` - analyze pediatric case
- `/api/save-attempt` - save student attempt
- `/api/dashboard/summary` - dashboard summary
- `/api/analytics/topics` - topic averages
- `/api/analytics/errors` - error distribution
- `/api/cases` - case library
