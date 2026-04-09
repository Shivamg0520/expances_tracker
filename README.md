# Expense Tracker (Flask + SQLite / PostgreSQL)

## Features
- User authentication (`/register`, `/login`, `/logout`)
- Add daily expenses (category, amount, date)
- Dashboard charts (Plotly + Matplotlib PNG)
- Export expenses to CSV (`/export`)
- Responsive UI (Bootstrap)

## Local setup (Windows PowerShell)
```powershell
cd C:\path\to\expances_tracker

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Local DB: SQLite by default (no DATABASE_URL)
$env:FLASK_SECRET_KEY="dev-secret-change-in-production"

python app.py
```

Open: `http://127.0.0.1:5000`

### Optional: local PostgreSQL
Install PostgreSQL, database banao, phir:
```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@localhost:5432/expenses_db"
$env:FLASK_SECRET_KEY="your-secret"
python app.py
```

## Deploy (GitHub + Render — free tier friendly)

1. Code GitHub repo me push karo.
2. [Render](https://render.com) par account banao → **New +** → **PostgreSQL** → database create karo (free tier).
3. **New +** → **Web Service** → GitHub repo connect karo.
4. Settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app` (ya `Procfile` auto-pick ho sakta hai)
5. **Environment** variables:
   - `FLASK_SECRET_KEY` — long random string (e.g. `openssl rand -hex 32` se)
   - `DATABASE_URL` — Render Postgres ke **Internal Database URL** ko copy karo (Web Service me add karo; Render kabhi `postgres://` deta hai, app automatically `postgresql://` me convert kar deti hai)
6. Deploy. Pehli deploy ke baad tables `db.create_all()` se ban jayengi.

**Note:** Production me `DEBUG` off rakho (abhi `app.run(debug=True)` sirf local `python app.py` ke liye hai).

## Files
- `Procfile` — `gunicorn app:app` (Heroku/Railway style hosts)
- `runtime.txt` — Python version hint (Render etc.)
