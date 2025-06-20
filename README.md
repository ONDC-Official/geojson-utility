# GeoJSON Backend API

A production-ready FastAPI backend for uploading, processing, and storing CSVs with geospatial data, user authentication, and JWT blacklist management.

## Features

- User registration, JWT issuance (no expiration)
- Login using JWT token only
- Upload and process CSVs with geospatial data (Lepton Maps API)
- Download processed CSVs (with geojson column)
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

## API Endpoints

### **POST /auth/register**
Register a new user and receive a JWT token (no expiration).
- **Request:** `{ "username": "string", "password": "string" }`
- **Response:** `{ "access_token": "...", "token_type": "bearer" }`
- **Authentication:** Not required
- **Curl:**
  ```sh
  curl -X POST http://localhost:8000/auth/register \
    -H 'Content-Type: application/json' \
    -d '{"username": "testuser1", "password": "testpass"}'
  ```

### **POST /auth/login**
Login using a JWT token only. Returns the username if valid.
- **Request:** `{ "token": "<jwt_token>" }`
- **Response:** `{ "username": "..." }`
- **Authentication:** Not required
- **Curl:**
  ```sh
  curl -X POST http://localhost:8000/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"token": "<jwt_token>"}'
  ```

### **POST /auth/logout**
Blacklist the current JWT token.
- **Request:** Bearer token in Authorization header
- **Response:** `{ "msg": "Logged out successfully" }`
- **Authentication:** Required
- **Curl:**
  ```sh
  curl -X POST http://localhost:8000/auth/logout \
    -H 'Authorization: Bearer <jwt_token>'
  ```

### **GET /catchment/sample-csv**
Download a sample CSV template for bulk upload.
- **Response:** CSV file (Content-Disposition: attachment)
- **Authentication:** Not required
- **Curl:**
  ```sh
  curl -O -J http://localhost:8000/catchment/sample-csv
  ```

### **POST /catchment/bulk**
Upload a CSV for bulk processing. Each row is validated and processed asynchronously.
- **Request:** Multipart form with a CSV file (`file=@sample.csv`)
- **Response:** `{ "csv_id": <id>, "status": "pending" }`
- **Authentication:** Required (Bearer token)
- **Curl:**
  ```sh
  curl -X POST http://localhost:8000/catchment/bulk \
    -H 'Authorization: Bearer <jwt_token>' \
    -F 'file=@sample.csv'
  ```
- **CSV and Field Validations:**
  - **File size:** Max 2MB
  - **Row count:** Max 1000 rows
  - **No duplicate rows allowed**
  - **Required columns:** `snp_id`, `provider_id`, `location_id`, `location_gps`, `drive_distance`, `drive_time`
  - **snp_id, provider_id, location_id:**
    - Non-empty string, max 255 characters
    - Only alphanumeric, underscore, and dash allowed
    - No leading/trailing whitespace
  - **location_gps:**
    - String with two comma-separated floats (latitude,longitude)
    - Each float must have at least 4 decimal places
    - Latitude must be between -90 and 90, longitude between -180 and 180
    - No extra whitespace
  - **drive_distance, drive_time:**
    - At least one must be provided and non-empty per row
    - Must be positive integers if present
    - `drive_distance` takes precedence if both are provided
    - Reasonable upper bounds: `drive_distance` ≤ 100,000, `drive_time` ≤ 10,000
  - **If any row fails validation, the entire file is marked as failed and errors are returned in the status endpoint.**
- **Sample CSV:**
  ```csv
  snp_id,provider_id,location_id,location_gps,drive_distance,drive_time
  sample_seller,sample_provider,L1,"12.3400,56.7800",500,
  another_seller,provider2,L2,"-45.1234,89.5678",,120
  ```
- **Error Reporting:**
  - If the file fails, `/catchment/csv-status/{csv_id}` returns:
    ```json
    {
      "csv_id": 1,
      "status": "failed",
      "error": "Row 2: drive_distance must be a positive integer.\nRow 3: location_gps must be a string with two comma-separated floats, each with at least 4 decimals, valid range, and no extra whitespace."
    }
    ```

### **GET /catchment/csv-status/{csv_id}**
Check the processing status of a CSV.
- **Response:** `{ "csv_id": <id>, "status": "pending|processing|done|failed", "error": "..." (if failed) }`
- **Authentication:** Required
- **Curl:**
  ```sh
  curl -X GET http://localhost:8000/catchment/csv-status/1 \
    -H 'Authorization: Bearer <jwt_token>'
  ```

### **GET /catchment/csv/{csv_id}**
Download the processed CSV by its ID (only available when status is `done`).
- **Response:** CSV file (Content-Disposition: attachment)
- **Authentication:** Required
- **Curl:**
  ```sh
  curl -X GET http://localhost:8000/catchment/csv/1 \
    -H 'Authorization: Bearer <jwt_token>' -O -J
  ```

### **GET /catchment/csvs**
List all uploaded/processed CSVs for the current user.
- **Response:** Array of CSV file metadata (id, filename, username, user_id, created_at)
- **Authentication:** Required
- **Curl:**
  ```sh
  curl -X GET http://localhost:8000/catchment/csvs \
    -H 'Authorization: Bearer <jwt_token>'
  ```

### **POST /admin/cleanup-blacklist**
Manually trigger cleanup of expired JWT blacklist entries (older than 7 days).
- **Response:** `{ "deleted": <number_of_entries_deleted> }`
- **Authentication:** Not required (but should be protected in production)
- **Curl:**
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
