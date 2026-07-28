# geojson-utility

A full-stack utility for bulk-enriching location data with geospatial catchment areas. Upload a CSV of locations, and the backend calls the [Lepton Maps API](https://leptonmaps.com/) to compute a drive-distance/drive-time catchment area for each row, returning the CSV augmented with a `geojson` column.

## Architecture

| Service    | Stack                                              | Details                          |
| ---------- | --------------------------------------------------- | --------------------------------- |
| `backend`  | FastAPI, SQLAlchemy, PostgreSQL, Alembic             | [backend/README.md](backend/README.md)   |
| `frontend` | Vite, React 18, TypeScript, Tailwind, shadcn/radix-ui | [frontend/README.md](frontend/README.md) |
| `db`       | PostgreSQL 15                                        | provisioned via Docker Compose    |

## Key features

- Upload a CSV of locations and process it asynchronously against the Lepton Maps API
- Row-level validation (coordinate format, IDs, drive distance/time, duplicates, size/row limits)
- Poll processing status per upload (`pending` → `processing` → `done`/`failed`)
- Download the processed CSV with the computed `geojson` column
- JWT-based authentication, rate limiting, and PostgreSQL-trigger/SSE-driven status updates

## Quick start (Docker Compose)

1. Copy the example environment file and fill in the required values (at minimum `LEPTON_API_KEY`, `SECRET_KEY`, and DB credentials):
   ```sh
   cp .env-example .env
   ```
2. Build and start all services:
   ```sh
   docker-compose up --build
   ```
3. The app will be available at:
   - Frontend: `http://localhost:7000`
   - Backend API: `http://localhost:8000`

For production, use `docker-compose-prod.yml` with a `.env-prod` file.

See [backend/README.md](backend/README.md) for local (non-Docker) setup, database migrations, and full API endpoint documentation, and [frontend/README.md](frontend/README.md) for frontend-only development.

## Environment variables

Defined in `.env-example`:

| Variable              | Purpose                                              |
| --------------------- | ----------------------------------------------------- |
| `SECRET_KEY`           | Signing key for auth tokens/sessions                   |
| `LEPTON_API_KEY`       | API key for the Lepton Maps geospatial service          |
| `GEOJSON_UTILITY_KEY`  | Shared secret required to register a new user            |
| `ENV`                  | `development`, `staging`, or `production`               |
| `CORS_ORIGINS`         | Comma-separated allowed origins, or `*`                 |
| `RATE_LIMIT`           | API rate limit (e.g. `100/minute`)                       |
| `VITE_API_BASE_URL`    | Backend base URL used by the frontend                    |
| `DB_USERNAME`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`/`DB_NAME` | PostgreSQL connection details |
| `DATABASE_URL`         | Full Postgres connection string built from the above      |
| `DEFAULT_USER_TOKENS`  | Default token allocation for new users                    |

## Project structure

```
.
├── backend/    # FastAPI service (API, DB models, migrations)
├── frontend/   # Vite/React app
├── docker-compose.yml       # local/dev orchestration
└── docker-compose-prod.yml  # production orchestration
```
