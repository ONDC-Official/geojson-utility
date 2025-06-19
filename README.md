# GeoJSON Backend API

A production-ready FastAPI backend for uploading, processing, and storing CSVs with geospatial data, user authentication, and JWT blacklist management.

## Features

- User registration, login, and logout (JWT-based)
- Upload CSVs and process each row with the Lepton Maps API
- Download processed CSVs (with geojson column for each row)
- List uploaded CSVs
- JWT blacklist with automatic cleanup (every 7 days)
- Admin endpoint for manual blacklist cleanup
- **Global webhook notification when CSV processing completes**

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
   WEBHOOK_URL=https://your-frontend-or-webhook-endpoint.com/webhook
   ```
3. **Run Alembic migrations:**

   ```sh
   alembic upgrade head
   ```
4. **Start the server:**

   ```sh
   uvicorn main:app --reload
   ```

## API Endpoints & Detailed Explanations

### **POST /auth/register**
**Register a new user.**
- **Request:** JSON `{ "username": "string", "password": "string" }`
- **Response:** User info (without password)
- **Authentication:** Not required
```sh
curl -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username": "testuser1", "password": "testpass"}'
```

### **POST /auth/login**
**Authenticate and get a JWT access token.**
- **Request:** JSON `{ "username": "string", "password": "string" }`
- **Response:** `{ "access_token": "...", "token_type": "bearer" }`
- **Authentication:** Not required
```sh
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "testuser1", "password": "testpass"}'
```

### **POST /auth/logout**
**Logout and blacklist the current JWT token.**
- **Request:** No body
- **Response:** `{ "msg": "Logged out successfully" }`
- **Authentication:** Required (Bearer token)
```sh
curl -X POST http://localhost:8000/auth/logout \
  -H 'Authorization: Bearer <access_token>'
```

### **GET /catchment/sample-csv**
**Download a sample CSV template for bulk upload.**
- **Request:** No body
- **Response:** CSV file (Content-Disposition: attachment)
- **Authentication:** Not required
```sh
curl -O -J http://localhost:8000/catchment/sample-csv
```

### **POST /catchment/bulk**
**Upload a CSV for bulk processing.**
- **Request:** Multipart form with a CSV file (`file=@sample.csv`)
- **Response:** `{ "csv_id": <id>, "status": "pending" }`
- **Authentication:** Required (Bearer token)
- **Notes:**
  - The CSV is processed asynchronously. Each row is enriched with a `geojson` column.
  - The status can be checked via `/catchment/csv-status/{csv_id}`.
```sh
curl -X POST http://localhost:8000/catchment/bulk \
  -H 'Authorization: Bearer <access_token>' \
  -F 'file=@sample.csv'
```

### **GET /catchment/csv-status/{csv_id}**
**Check the processing status of a CSV.**
- **Request:** No body
- **Response:** `{ "csv_id": <id>, "status": "pending|processing|done|failed" }`
- **Authentication:** Required (Bearer token)
```sh
curl -X GET http://localhost:8000/catchment/csv-status/1 \
  -H 'Authorization: Bearer <access_token>'
```

### **GET /catchment/csv/{csv_id}**
**Download the processed CSV by its ID.**
- **Request:** No body
- **Response:** CSV file (Content-Disposition: attachment)
- **Authentication:** Required (Bearer token)
- **Notes:** Only available when status is `done`.
```sh
curl -X GET http://localhost:8000/catchment/csv/1 \
  -H 'Authorization: Bearer <access_token>' -O -J
```

### **GET /catchment/csvs**
**List all uploaded/processed CSVs for the current user.**
- **Request:** No body
- **Response:** Array of CSV file metadata (id, filename, username, user_id, created_at)
- **Authentication:** Required (Bearer token)
```sh
curl -X GET http://localhost:8000/catchment/csvs \
  -H 'Authorization: Bearer <access_token>'
```

### **POST /admin/cleanup-blacklist**
**Manually trigger cleanup of expired JWT blacklist entries (older than 7 days).**
- **Request:** No body
- **Response:** `{ "deleted": <number_of_entries_deleted> }`
- **Authentication:** Not required (but should be protected in production)
```sh
curl -X POST http://localhost:8000/admin/cleanup-blacklist
```

## Webhook Notification on CSV Processing

When a CSV is processed and status is set to `done`, the backend will automatically send a POST request to the global webhook URL specified in your `.env` as `WEBHOOK_URL`.

- **Payload Example:**
  ```json
  {
    "csv_id": 1,
    "status": "done",
    "download_url": "http://localhost:8000/catchment/csv/1"
  }
  ```
- **How to test:**
  1. Set `WEBHOOK_URL` in your `.env` to a test endpoint (e.g., from https://webhook.site/).
  2. Upload a CSV and wait for processing to complete.
  3. Check your test endpoint for the POST request.

## Notes

- All endpoints requiring authentication need the `Authorization: Bearer <access_token>` header.
- The JWT blacklist is cleaned up automatically on server startup and can be triggered manually via the admin endpoint.
- Use Alembic for all future database schema changes.
