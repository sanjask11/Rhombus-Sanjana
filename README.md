# Rhombus AI – Data Type Inference Engine

A full-stack web application that connects to Amazon S3, loads CSV/Excel datasets, and automatically infers & converts data types using an enhanced Pandas pipeline.

## Architecture

```
frontend/   React (Vite) – S3 browser, data table, type override UI
backend/    Django REST Framework – S3 connector, type inference, history
```

## Features

- **S3 Integration** – connect to any S3 bucket, browse CSV/Excel files
- **Enhanced Type Inference** – Boolean → Numeric → Complex → Datetime → Categorical → Text
- **Mixed-type tolerance** – columns with ≤20 % non-parseable values still infer correctly (e.g. "Not Available" in a numeric column becomes `null`)
- **User overrides** – change any column's type via dropdown and re-process
- **Processing history** – last 20 processed files stored in SQLite
- **Large file support** – uses sample-based inference (10 k rows) for speed

## Prerequisites

- Python ≥ 3.10
- Node.js ≥ 18
- AWS credentials with `s3:GetObject` + `s3:ListBucket` on your bucket

---

## Local Setup

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in SECRET_KEY + AWS credentials

python manage.py migrate
python manage.py runserver      # http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The Vite dev server proxies `/api` → `http://localhost:8000`, so no CORS issues locally.

---

## Environment Variables (backend/.env)

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for development |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins |
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_DEFAULT_REGION` | S3 region (default `us-east-1`) |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/s3/files/?bucket=<name>` | List CSV/Excel files in bucket |
| `POST` | `/api/process/` | Infer types & return data preview |
| `GET` | `/api/history/` | Last 20 processed files |

### POST `/api/process/` body

```json
{
  "bucket": "my-bucket",
  "file_key": "data/sales.csv",
  "type_overrides": {
    "Score": "integer",
    "Birthdate": "datetime64"
  }
}
```

---

## Type Inference Logic

Priority order applied per column:

1. **Boolean** – all unique values ∈ `{true/false, yes/no, 1/0, t/f, on/off, y/n}` (case-insensitive)
2. **Numeric** – `pd.to_numeric` succeeds for ≥80 % of values; auto-downcasted to smallest int/float
3. **Complex** – values match complex number pattern (`3+4j`, `(1,2)`)
4. **Datetime** – tries 20+ format strings, falls back to flexible `format='mixed'`
5. **Categorical** – unique/total ratio < 0.5
6. **Text** – default

Integer columns with NaN use pandas nullable `Int64` dtype.

---

## Deployment

### Backend (e.g. Railway / Render)

```bash
pip install gunicorn
gunicorn rhombus_backend.wsgi:application --bind 0.0.0.0:$PORT
```

Set `DEBUG=False`, `ALLOWED_HOSTS=yourdomain.com`, and add your frontend origin to `CORS_ALLOWED_ORIGINS`.

### Frontend (e.g. Vercel / Netlify)

```bash
cd frontend
npm run build   # outputs to frontend/dist/
```

Set `VITE_API_BASE=https://your-backend.com/api` in the deployment environment.
