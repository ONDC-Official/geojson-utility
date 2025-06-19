# GeoJSON Backend API

A production-ready FastAPI backend for uploading, processing, and storing CSVs with geospatial data, user authentication, and JWT blacklist management.

## Features

- User registration, login, and logout (JWT-based)
- Upload CSVs and process each row with the Lepton Maps API
- Download processed CSVs (with geojson column for each row)
- List uploaded CSVs
- JWT blacklist with automatic cleanup (every 7 days)
- Admin endpoint for manual blacklist cleanup

## Setup

1. **Clone the repo and install dependencies:**

   ```sh
   pip install -r requirements.txt
   ```
2. **Set environment variables in a `.env` file:**

   ```env
   DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<database>
   SECRET_KEY=your_secret_key
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   LEPTON_API_KEY=your_leptonmaps_api_key
   ```
3. **Run Alembic migrations:**

   ```sh
   alembic upgrade head
   ```
4. **Start the server:**

   ```sh
   uvicorn main:app --reload
   ```

## API Endpoints & Curl Examples

### Register

```sh
curl -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username": "testuser1", "password": "testpass"}'
```

### Login

```sh
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "testuser1", "password": "testpass"}'
```

Response: `{ "access_token": "...", "token_type": "bearer" }`

### Logout

```sh
curl -X POST http://localhost:8000/auth/logout \
  -H 'Authorization: Bearer <access_token>'
```

### Upload CSV (Bulk Process)

```sh
curl -X POST http://localhost:8000/catchment/bulk \
  -H 'Authorization: Bearer <access_token>' \
  -F 'file=@sample.csv'
```

- The processed CSV (with a `geojson` column for each row) is returned and also stored in the database.

### Download Sample CSV

```sh
curl -O -J http://localhost:8000/catchment/sample-csv
```

### Download Processed CSV by ID

```sh
curl -X GET http://localhost:8000/catchment/csv/1 \
  -H 'Authorization: Bearer <access_token>' -O -J
```

- Returns the processed CSV (with `geojson` column) for the given file ID.

### List Uploaded CSVs

```sh
curl -X GET http://localhost:8000/catchment/csvs \
  -H 'Authorization: Bearer <access_token>'
```

- Lists all uploaded/processed CSVs for the current user (by user ID) with their IDs, filenames, uploader, and upload time.

### Admin: Cleanup JWT Blacklist

```sh
curl -X POST http://localhost:8000/admin/cleanup-blacklist
```

## Notes

- All endpoints requiring authentication need the `Authorization: Bearer <access_token>` header.
- The JWT blacklist is cleaned up automatically on server startup and can be triggered manually via the admin endpoint.
- Use Alembic for all future database schema changes.
