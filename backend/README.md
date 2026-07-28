# GeoJSON Backend API

A FastAPI backend for uploading, processing, and storing CSVs with geospatial data. Each row's coordinates are enriched with a drive-distance/drive-time catchment-area GeoJSON via the [Lepton Maps API](https://leptonmaps.com/).

## Features

- Upload and process CSVs with geospatial data (Lepton Maps API)
- Per-user token-based rate limiting against the Lepton API, with concurrency-safe token accounting
- Download processed CSVs (with `geojson` and `errors` columns)
- List uploaded CSVs and view per-user dashboard stats
- Live processing status via polling or Server-Sent Events (SSE)

## Project structure

```
backend/
├── main.py            # FastAPI app, middleware, router registration
├── core/               # auth, password hashing, rate limiting, SSE manager, Lepton token accounting, CSV row validation
├── crud/               # DB access helpers (users)
├── db/                 # engine/session setup, Postgres LISTEN/NOTIFY trigger setup
├── models/              # SQLAlchemy models (User, CSVFile)
├── routers/             # /auth, /catchment, /user-dashboard endpoints
├── schemas/             # Pydantic request/response schemas
└── alembic/              # DB migrations
```

## Authentication model

There's no traditional username/password login endpoint. Instead:

1. **`POST /auth/register`** creates a user and returns a non-expiring JWT (`access_token`), which is also stored on the user row.
2. Share that token with the user out-of-band; they "log in" by pasting it into the app, which calls **`POST /auth/login`** with `{ "token": "..." }` to validate it and get back a hashed form of the token used for the SSE endpoint (see below).
3. All other endpoints require `Authorization: Bearer <jwt_token>`.

> Registration is gated by a shared static secret (`GEOJSON_UTILITY_KEY` header) rather than being self-service.

## Setup

### Local Development

1. **Clone the repo and install dependencies** (run from `backend/`):
   ```sh
   cd backend
   pip install -r requirements.txt
   ```
2. **Set environment variables in a `.env` file** (see [Environment variables](#environment-variables) below for the full list).
3. **Run migrations** (from `backend/`):
   ```sh
   alembic upgrade head
   ```
4. **Start the backend** (from `backend/`):
   ```sh
   uvicorn main:app --reload
   ```

### Docker Compose

1. **From the repo root, build and start the services:**
   ```sh
   docker-compose up --build
   ```
2. **The API will be available at** `http://localhost:8000`

## Environment variables

| Variable               | Required | Description                                                              |
| ----------------------- | -------- | -------------------------------------------------------------------------- |
| `SECRET_KEY`             | Yes      | Signing key for JWTs                                                        |
| `LEPTON_API_KEY`         | Yes      | API key for the Lepton Maps catchment API                                    |
| `GEOJSON_UTILITY_KEY`    | Yes      | Shared secret required in the `geojson-utility-key` header to register a user |
| `DB_USERNAME` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` / `DB_NAME` | Yes | PostgreSQL connection details |
| `DATABASE_URL`           | Yes      | Full Postgres connection string, normally built from the vars above           |
| `CORS_ORIGINS`           | No       | Comma-separated allowed origins, or `*` (default `*`)                          |
| `RATE_LIMIT`             | No       | Default rate limit for undecorated routes (default `100/minute`)               |
| `DEFAULT_USER_TOKENS`    | No       | Lepton-call token allocation given to new users (default `20`)                 |
| `ENV`                    | No       | `development` or `production` (default `production`). Swagger docs are only served at `/swagger-docs` when `development`. |

## API Endpoints

Interactive docs are available at `GET /swagger-docs` when `ENV=development`. A basic health check is available at `GET /health`.

### Auth (`/auth`)

#### **POST /auth/register**
Create a user (requires the shared registration key) and receive a JWT.
- **Headers:** `geojson-utility-key: <GEOJSON_UTILITY_KEY>`
- **Body:** `{ "username": "...", "password": "..." }`
- **Response:** `{ "access_token": "...", "token_type": "bearer" }`

#### **POST /auth/login** — rate limited to 5/minute
Validate a previously issued token and get a hashed form of it for the SSE endpoint.
- **Body:** `{ "token": "<jwt_token>" }`
- **Response:** `{ "username": "...", "hashed_token": "..." }`

#### **GET /auth/token-status**
Get the current user's Lepton API token allocation and usage.
- **Authentication:** Required (Bearer token)
- **Response:** `{ "user_id": ..., "username": "...", "tokens": { "used": ..., "limit": ..., "remaining": ... } }`

#### **POST /auth/delete-user**
Delete the current user and their data.
- **Authentication:** Required (Bearer token)

### Catchment (`/catchment`)

#### **GET /catchment/sample-csv**
Download a sample CSV template for bulk upload.
- **Response:** CSV file (Content-Disposition: attachment)
- **Authentication:** Not required
- **Curl:**
  ```sh
  curl -O -J http://localhost:8000/catchment/sample-csv
  ```

#### **POST /catchment/bulk** — rate limited to 10/minute
Upload a CSV for bulk processing. Each row is validated and processed asynchronously.
- **Request:** Multipart form with a CSV file (`file=@sample.csv`)
- **Response:** `{ "csv_id": <id>, "status": "pending", "token_info": { "available": ..., "total_rows": ..., "estimated_processed": ... } }`
- **Authentication:** Required (Bearer token)
- **Curl:**
  ```sh
  curl -X POST http://localhost:8000/catchment/bulk \
    -H 'Authorization: Bearer <jwt_token>' \
    -F 'file=@sample.csv'
  ```
- **CSV and Field Validations:**
  - **File size:** Max 10MB
  - **Row count:** Max 1000 rows
  - **No duplicate rows allowed**
  - **No duplicate `location_id` values allowed**
  - **Required columns:** `snp_id`, `provider_id`, `location_id`, `location_gps`, `drive_distance`, `drive_time`
  - **snp_id, provider_id, location_id:**
    - Non-empty string, max 255 characters
    - Only alphanumeric, underscore, dash, dot, `@`, and `/` allowed
    - No leading/trailing whitespace
  - **location_gps:**
    - String with two comma-separated floats (latitude,longitude)
    - Each float must have at least 4 decimal places
    - Latitude must be between -90 and 90, longitude between -180 and 180
  - **drive_distance, drive_time:**
    - At least one must be provided and non-empty per row
    - Must be positive numbers if present (accepts both `500` and `500.0`)
    - `drive_distance` takes precedence if both are provided
    - Reasonable upper bounds: `drive_distance` ≤ 100,000, `drive_time` ≤ 10,000
  - Rows are processed against the user's remaining Lepton API token allocation; once tokens run out, remaining rows fail with `"Your token allocation has been exhausted"` and the CSV is marked `partial`.
  - **Sample CSV:**
    ```csv
    snp_id,provider_id,location_id,location_gps,drive_distance,drive_time
    sample_seller,sample_provider,L1,"28.5065162,77.073938",500,
    sample_seller,sample_provider,L2,"30.7135305,76.7454157",,20
    ```
  - **Error Reporting:**
    - If the file fails, `/catchment/csv-status/{csv_id}` returns:
      ```json
      {
        "csv_id": 1,
        "status": "failed",
        "error": "Row 2: drive_distance must be a positive integer.\nRow 3: location_gps must be a string with two comma-separated floats, each with at least 4 decimals, valid range."
      }
      ```

#### **GET /catchment/csv-status/{csv_id}**
Check the processing status of a CSV.
- **Response:** `{ "csv_id": <id>, "status": "pending|processing|done|partial|failed", "error": "..." (if failed) }`
- **Authentication:** Required
- **Curl:**
  ```sh
  curl -X GET http://localhost:8000/catchment/csv-status/1 \
    -H 'Authorization: Bearer <jwt_token>'
  ```

#### **GET /catchment/csv-status-stream/{csv_id}**
Stream real-time processing status via Server-Sent Events, backed by a PostgreSQL `LISTEN/NOTIFY` trigger on `csv_files`. Because browser `EventSource` can't send custom headers, auth is passed via query params instead of a Bearer token.
- **Query params:** `hashed_token` (SHA-256 of the JWT, see `/auth/login`), `username`
- **Authentication:** Required (via query params, as above)
- **Response:** `text/event-stream` of JSON events (`init`, `start`, `progress`, `complete`, `heartbeat`)

#### **GET /catchment/csv/{csv_id}**
Download the processed CSV by its ID (only available once status is `done`, `partial`, or `failed`).
- **Response:** CSV file (Content-Disposition: attachment)
- **Authentication:** Required
- **Curl:**
  ```sh
  curl -X GET http://localhost:8000/catchment/csv/1 \
    -H 'Authorization: Bearer <jwt_token>' -O -J
  ```

#### **GET /catchment/csvs**
List all uploaded/processed CSVs for the current user.
- **Response:** Array of CSV file metadata (id, filename, username, user_id, created_at)
- **Authentication:** Required
- **Curl:**
  ```sh
  curl -X GET http://localhost:8000/catchment/csvs \
    -H 'Authorization: Bearer <jwt_token>'
  ```

### Dashboard (`/user-dashboard`)

#### **GET /user-dashboard/stats**
Paginated upload/download stats for the current user.
- **Query params:** `page` (default 1), `per_page` (default 10)
- **Authentication:** Required (Bearer token)

## Usage

- Register (or receive a token) and log in to get a Bearer token, upload CSVs, check status (via polling or SSE), and download processed files via the documented endpoints.
