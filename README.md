# Rhombus AI — Data Type Inference Engine

A full-stack web application that connects to Amazon S3, loads CSV/Excel
datasets, and automatically infers and converts each column to the most
appropriate data type using an enhanced pandas pipeline. The inferred
types are presented in a React UI where the user can review, override,
and re-process the file.

---

## Features

- **S3 integration** — list and load CSV/Excel files from any bucket the configured AWS credentials have access to
- **Seven-tier inference pipeline** — Boolean → Numeric → Complex → Datetime → Timedelta → Categorical → Text
- **Mixed-data tolerance** — columns with up to 20% non-parseable values still infer correctly (`"Not Available"` in a numeric column becomes a nullable `Int64` with one `NaN`)
- **Per-column overrides** — change any inferred type from a dropdown and re-run inference without re-uploading
- **CSV encoding fallback** — UTF-8, UTF-8-BOM, latin-1, and cp1252 are tried in order so files exported from Excel or Windows just work
- **Memory-aware downcasting** — integer columns are downcast to the smallest dtype that fits (`uint8`, `int16`, etc.); float columns whose values are all whole numbers are converted to integer
- **Sample-based inference** — large datasets sample 10 000 rows for type detection to keep response times low
- **Processing history** — the last 20 processed files are stored in SQLite and shown in the UI
- **84 automated tests** — pytest coverage across the inference engine, the S3 client (using `moto`), the API endpoints, and the seven checked-in fixture CSVs

---

## Tech Stack

| Layer | Stack |
|---|---|
| Frontend | React 18, Vite 5 |
| Backend | Django 4.2, Django REST Framework |
| Inference | pandas 2.x, numpy |
| Storage | Amazon S3 (boto3), SQLite for history |
| Testing | pytest, pytest-django, moto |

---

## Prerequisites

- Python ≥ 3.10
- Node.js ≥ 18
- An AWS account with a bucket containing CSV or Excel files
- An IAM user with `s3:ListBucket` and `s3:GetObject` permissions on that bucket

---

## Quick Start

The application runs as two processes: a Django backend on port 8000 and a Vite dev server on port 5173. The Vite proxy forwards `/api/*` to the backend, so no CORS configuration is needed during development.

### 1. Clone and enter the project

```bash
git clone https://github.com/sanjask11/Rhombus-Sanjana.git
cd Rhombus-Sanjana
```

### 2. Backend setup

Create a virtual environment, install dependencies, copy the environment template, and run database migrations:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
```

Open `backend/.env` and fill in your AWS credentials and a Django secret key. See [Configuration](#configuration) for the full list of variables.

Start the backend server:

```bash
python manage.py runserver
```

The API is now live at `http://localhost:8000/api/`.

### 3. Frontend setup

In a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Enter the name of an S3 bucket you own, pick a CSV/Excel file, and the inferred types appear alongside the data preview.

### 4. (Optional) Upload the bundled test data

Seven curated CSVs covering every inference path live in `backend/test_data/`. Upload them all to a bucket of your choice with:

```bash
python scripts/upload_test_data.py your-bucket-name
```

See [Test Data](#test-data) for the per-file inference matrix.

---

## Configuration

All backend configuration lives in `backend/.env`. Copy from `.env.example` and fill in:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | yes | Django secret key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | yes | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | yes | Comma-separated hostnames the backend will serve |
| `CORS_ALLOWED_ORIGINS` | yes | Comma-separated frontend origins |
| `AWS_ACCESS_KEY_ID` | yes | IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | yes | IAM user secret key |
| `AWS_DEFAULT_REGION` | yes | The region your bucket lives in (e.g. `us-east-1`) |

The frontend reads its API base from `frontend/.env` (only needed for production builds):

| Variable | Description |
|---|---|
| `VITE_API_BASE` | Full URL of the deployed backend, e.g. `https://your-backend.com/api` |

In development the Vite proxy handles routing, so this is not required.

---

## Project Structure

```
Rhombus-Sanjana/
├── README.md
├── .gitignore
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   │
│   ├── rhombus_backend/         Django project configuration
│   │   ├── settings.py
│   │   └── urls.py
│   │
│   ├── data_processor/          Main Django app
│   │   ├── infer_data_types.py  The seven-tier inference pipeline
│   │   ├── s3_utils.py          boto3 wrapper with encoding fallback
│   │   ├── views.py             REST API endpoints
│   │   ├── serializers.py       Request validation
│   │   ├── models.py            ProcessingHistory database model
│   │   ├── urls.py              Route definitions
│   │   └── tests/               84 pytest cases across 5 files
│   │
│   ├── test_data/               7 fixture CSVs covering every type
│   │   └── README.md            Per-file inference matrix
│   │
│   └── scripts/
│       └── upload_test_data.py  Bulk upload fixtures to S3
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js           Dev proxy: /api → localhost:8000
    └── src/
        ├── main.jsx
        ├── App.jsx              Top-level component
        ├── api/api.js           Fetch wrappers
        └── components/
            ├── S3Browser.jsx    Bucket input + file list
            └── DataPreview.jsx  Inferred-type table with override dropdowns
```

---

## How It Works

A single request to `POST /api/process/` flows through five stages:

1. **Validation** — `ProcessFileSerializer` checks that `bucket`, `file_key` are non-empty and that any keys in `type_overrides` map to a known target type from the supported list.
2. **Download** — `S3Client.load_file()` fetches the object from S3 and parses it into a pandas DataFrame. CSVs are tried against four encodings in order (UTF-8, UTF-8-BOM, latin-1, cp1252) so non-ASCII files load without manual intervention.
3. **Inference** — `infer_and_convert_data_types()` walks every column through the priority chain. Any column listed in `type_overrides` short-circuits inference and uses the forced type instead.
4. **Serialization** — `get_type_info()` produces per-column metadata (display type, null count, unique count, sample values), and `_df_to_records()` returns the first 100 rows as JSON, handling the dtypes (`datetime64`, `boolean`, `complex`, `category`) that are not natively JSON-serializable.
5. **Persistence** — A `ProcessingHistory` row is created with the bucket, file key, row count, and inferred column types. Failures here are logged but do not break the response.

The frontend is intentionally thin: `S3Browser` calls `GET /api/s3/files/`, `DataPreview` calls `POST /api/process/` and renders the table, and the override dropdown re-issues the same `POST` with a populated `type_overrides` map.

---

## API Reference

### `GET /api/s3/files/?bucket=<name>`

Lists every CSV and Excel file in the given bucket, sorted newest first. Files with other extensions are filtered out.

**Response**

```json
{
  "bucket": "my-bucket",
  "files": [
    {
      "key": "data/sales.csv",
      "name": "sales.csv",
      "size": 12480,
      "size_display": "12.2 KB",
      "last_modified": "2024-09-12T18:24:00+00:00",
      "file_type": "csv"
    }
  ]
}
```

### `POST /api/process/`

Loads a file, runs inference (with optional overrides), and returns the column metadata plus a 100-row preview.

**Request body**

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

`type_overrides` is optional. Supported override values: `integer`, `decimal`, `boolean`, `datetime64`, `timedelta`, `category`, `text`, `complex` (plus aliases — see `serializers.SUPPORTED_OVERRIDE_TYPES`).

**Response**

```json
{
  "file_name": "sales.csv",
  "total_rows": 1042,
  "preview_rows": 100,
  "columns": [
    {
      "name": "Score",
      "dtype": "Int64",
      "display_type": "Integer",
      "null_count": 1,
      "unique_count": 87,
      "sample_values": ["90", "75", "85", "70", "65"]
    }
  ],
  "data": [ /* first 100 rows as JSON objects */ ]
}
```

### `GET /api/history/`

Returns the last 20 processed files.

```json
{
  "history": [
    {
      "id": 7,
      "bucket": "my-bucket",
      "file_name": "sales.csv",
      "file_key": "data/sales.csv",
      "total_rows": 1042,
      "processed_at": "2024-09-12T18:25:01+00:00",
      "column_count": 8
    }
  ]
}
```

---

## Type Inference Logic

Each column is evaluated in priority order. The first rule that matches wins, and a rule "matches" only when at least 80% of the column's non-null values can be coerced to the target type.

| Step | Type | Detection rule |
|---|---|---|
| 1 | **Boolean** | Every value is a recognized boolean token: `true/false`, `yes/no`, `t/f`, `on/off`, `y/n`. Pure `0`/`1` columns are deliberately skipped here so they fall to step 2 |
| 2 | **Numeric** | `pd.to_numeric` succeeds for ≥80% of values; the result is downcast to the smallest dtype that fits (`uint8`, `int16`, `int64`, etc.). Float columns whose values are all whole numbers become integers |
| 3 | **Complex** | At least 80% of values match a complex-number pattern such as `3+4j`, `5j`, or `(1, 2)` |
| 4 | **Datetime** | One of 19 explicit format strings parses ≥80% of values, or pandas' flexible parser does |
| 5 | **Timedelta** | At least 80% of values contain explicit duration hints (`days`, `hours`, `5h`, `30m`, ISO `P…`). Pure `HH:MM:SS` strings are intentionally excluded — they are usually meant as time-of-day |
| 6 | **Categorical** | Unique-to-total ratio is below 0.5 |
| 7 | **Text** | Default fallback |

Integer columns containing nulls use pandas' nullable `Int64` dtype rather than `float64`, which is the canonical fix for the `"Not Available"`-in-a-Score-column problem from the assignment brief.

---

## Running Tests

The full suite runs in under two seconds. From `backend/`, with the virtual environment active:

```bash
python -m pytest
```

For verbose output or to target one file:

```bash
python -m pytest -v
python -m pytest data_processor/tests/test_infer_data_types.py
```

The suite is organized into five files:

| File | What it covers |
|---|---|
| `test_infer_data_types.py` | Unit tests for every inference branch and override |
| `test_s3_utils.py` | S3 client, including the encoding fallback (uses `moto` to mock AWS) |
| `test_views.py` | End-to-end API tests with a mocked S3 backend |
| `test_sample_fixtures.py` | Asserts that every checked-in CSV in `test_data/` infers exactly the documented types |
| `conftest.py` | Shared fixtures: mocked S3 client, pre-populated bucket |

---

## Test Data

`backend/test_data/` contains seven curated CSVs designed to exercise every inference path. Use them as a quick QA catalog after deploying:

| File | What it tests |
|---|---|
| `all_types.csv` | The showcase — Integer, Text, Boolean, nullable Int64, Category, Decimal, Date/Time, Time Delta in one file |
| `sales.csv` | Realistic order data with downcast integers, Category (product), Boolean (shipped), Date/Time |
| `signals.csv` | Complex numbers and ISO-with-timezone datetimes |
| `boolean_formats.csv` | Every boolean token in the lookup map, including mixed case |
| `datetime_formats.csv` | Every format in the explicit `DATETIME_FORMATS` list |
| `edge_cases.csv` | Scientific notation, negatives, sparse nulls, high-cardinality text |
| `messy_encoding.csv` | latin-1 bytes (café, naïve, Zürich) — proves the encoding fallback |

Upload the whole set in one shot:

```bash
python scripts/upload_test_data.py your-bucket-name
```

---

## Deployment

### Backend (Render, Railway, Fly.io)

Install the production WSGI server and run:

```bash
pip install gunicorn
gunicorn rhombus_backend.wsgi:application --bind 0.0.0.0:$PORT
```

In the deployment environment, set:

- `DEBUG=False`
- `ALLOWED_HOSTS=your-domain.com`
- `CORS_ALLOWED_ORIGINS=https://your-frontend.com`
- All `AWS_*` variables

### Frontend (Vercel, Netlify)

```bash
cd frontend
npm run build
```

Set `VITE_API_BASE=https://your-backend.com/api` in the deployment environment so the built bundle knows where to call.

---

## License

Built as a take-home submission for Rhombus AI. Educational use only.
