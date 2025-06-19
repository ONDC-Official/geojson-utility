from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response, Request
from sqlalchemy.orm import Session
from core.auth import get_current_user
from db.session import get_db, Base, engine
from fastapi.responses import StreamingResponse, JSONResponse
from models.csvfile import CSVFile
import pandas as pd
import io
import os
import json
import http.client
from urllib.parse import urlencode
import logging
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.limiter import limiter
import threading
import httpx

load_dotenv()

# Ensure the csv_files and csv_rows tables exist
Base.metadata.create_all(bind=engine)

# Logger setup
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class LeptonMapsClient:
    HOST = "api.leptonmaps.com"
    PATH = "/v1/geojson/catchment"

    def __init__(self, api_key: str):
        self.headers = {
            "x-api-key": api_key,
            "Accept": "application/json"
        }
        self.conn = http.client.HTTPSConnection(self.HOST)

    def get_catchment_geojson(self, latitude: float, longitude: float, catchment_type: str = "DRIVE_DISTANCE", accuracy_time_based: str = "HIGH", drive_distance: int = 500, drive_time: Optional[int] = None, departure_time: Optional[str] = None) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "catchment_type": catchment_type,
            "accuracy_time_based": accuracy_time_based,
            "drive_distance": drive_distance
        }
        if drive_time is not None:
            params["drive_time"] = drive_time
        if departure_time is not None:
            params["departure_time"] = departure_time
        query_string = urlencode(params)
        full_path = f"{self.PATH}?{query_string}"
        logger.info(f"Requesting catchment: {full_path}")
        try:
            self.conn.request("GET", full_path, headers=self.headers)
            resp = self.conn.getresponse()
            body = resp.read()
            body_text = body.decode()
            if resp.status == 401:
                logger.error("HTTP 401: Unauthorized - Lepton Maps API key is invalid or expired")
                raise HTTPException(status_code=401, detail="Lepton Maps API: Unauthorized (HTTP 401). Your API key is invalid or expired.")
            if resp.status == 403:
                logger.error("HTTP 403: Forbidden - Lepton Maps API key is not allowed")
                raise HTTPException(status_code=403, detail="Lepton Maps API: Forbidden (HTTP 403). Your API key does not have access.")
            if resp.status == 402:
                logger.error("HTTP 402: Not enough credits on Lepton Maps API")
                raise HTTPException(status_code=402, detail="Lepton Maps API: Not enough credits (HTTP 402). Please check your API quota or upgrade your plan.")
            if resp.status != 200:
                logger.error(f"HTTP {resp.status}: {body_text}")
                raise HTTPException(status_code=resp.status, detail=f"Lepton Maps API: Unexpected status {resp.status}: {body_text}")
            geojson = json.loads(body)
            logger.info("Successfully fetched catchment GeoJSON")
            return geojson
        except Exception as e:
            logger.exception("Failed to fetch catchment")
            raise

    def extract_polygon_geojson(self, geojson: dict) -> dict:
        features = geojson.get("features", [])
        if not features:
            raise ValueError("No features found in GeoJSON response")
        geom = features[0].get("geometry", {})
        coords = geom.get("coordinates")
        if not coords or not isinstance(coords, list):
            raise ValueError("Invalid or missing coordinates in geometry")
        outer_ring = coords[0]
        polygon_coordinates = [(lat, lon) for lon, lat in outer_ring]
        geojson_polygon = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [polygon_coordinates]
                    },
                    "properties": {}
                }
            ]
        }
        return geojson_polygon

router = APIRouter(prefix="/catchment", tags=["catchment"])

@router.get("/sample-csv")
def get_sample_csv():
    output = io.StringIO()
    SAMPLE_CSV_ROW = {
    'seller_id': ['sample_seller'],
    'provider_id': ['sample_provider'],
    'lat': [28.6139],
    'long': [77.2090]}
    sample_df = pd.DataFrame(SAMPLE_CSV_ROW)
    sample_df.to_csv(output, index=False)
    output.seek(0)
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sample_catchment.csv"})

@router.post("/bulk")
@limiter.limit("10/minute")
async def bulk_process_catchments(request: Request, file: UploadFile = File(...), current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="CSV file is empty.")
    username = current_user.get('username')
    user_id = current_user.get('user_id') if 'user_id' in current_user else None
    # Save file as pending
    new_csv = CSVFile(filename=file.filename, file_content=content, username=username, user_id=user_id, status='pending')
    db.add(new_csv)
    db.commit()
    db.refresh(new_csv)
    csv_id = new_csv.id
    # Start background processing
    def process_csv_in_background(csv_id, content, username, user_id):
        session = next(get_db())
        try:
            csv_file = session.query(CSVFile).filter(CSVFile.id == csv_id).first()
            if not csv_file:
                return
            csv_file.status = 'processing'
            session.commit()
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
            required_columns = {'seller_id', 'provider_id', 'lat', 'long'}
            missing_columns = required_columns - set(df.columns)
            if missing_columns:
                csv_file.status = 'failed'
                session.commit()
                return
            errors = []
            geojson_results = [None] * len(df)
            api_key = os.environ.get("LEPTON_API_KEY")
            if not api_key:
                csv_file.status = 'failed'
                session.commit()
                return
            def process_row(idx, row):
                row_errors = []
                seller_id = row['seller_id']
                provider_id = row['provider_id']
                try:
                    lat = float(row['lat'])
                    if not (-90 <= lat <= 90):
                        row_errors.append(f"lat must be between -90 and 90.")
                except Exception:
                    row_errors.append(f"lat must be a valid float.")
                    lat = None
                try:
                    lon = float(row['long'])
                    if not (-180 <= lon <= 180):
                        row_errors.append(f"long must be between -180 and 180.")
                except Exception:
                    row_errors.append(f"long must be a valid float.")
                    lon = None
                if not isinstance(seller_id, str) or not seller_id:
                    row_errors.append("seller_id must be a non-empty string.")
                if not isinstance(provider_id, str) or not provider_id:
                    row_errors.append("provider_id must be a non-empty string.")
                geojson_str = '{}'
                if not row_errors and lat is not None and lon is not None:
                    try:
                        client = LeptonMapsClient(api_key=api_key)
                        geojson = client.get_catchment_geojson(latitude=lat, longitude=lon)
                        polygon_geojson = client.extract_polygon_geojson(geojson)
                        geojson_str = json.dumps(polygon_geojson)
                    except Exception as e:
                        logger.error(f"GeoJSON error for row {idx+1}: {str(e)}")
                        row_errors.append(f"GeoJSON error: {str(e)}")
                return idx, geojson_str, row_errors
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(process_row, idx, row) for idx, row in df.iterrows()]
                for future in as_completed(futures):
                    idx, geojson_str, row_errors = future.result()
                    geojson_results[idx] = geojson_str
                    if row_errors:
                        errors.append(f"Row {idx+1}: {'; '.join(row_errors)}")
            if errors:
                csv_file.status = 'failed'
                session.commit()
                return
            df['geojson'] = geojson_results
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            processed_content = output.getvalue().encode('utf-8')
            csv_file.file_content = processed_content
            csv_file.status = 'done'
            session.commit()
            # Send webhook after processing is done
            webhook_url = os.getenv("WEBHOOK_URL")
            if webhook_url:
                try:
                    download_url = f"http://localhost:8000/catchment/csv/{csv_id}"
                    payload = {
                        "csv_id": csv_id,
                        "status": "done",
                        "download_url": download_url
                    }
                    response = httpx.post(webhook_url, json=payload, timeout=5)
                    response.raise_for_status()
                    logger.info(f"Webhook sent to {webhook_url}")
                except Exception as e:
                    logger.error(f"Failed to send webhook: {e}")
            else:
                logger.info("No WEBHOOK_URL set, skipping webhook.")
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            csv_file = session.query(CSVFile).filter(CSVFile.id == csv_id).first()
            if csv_file:
                csv_file.status = 'failed'
                session.commit()
        finally:
            session.close()
    threading.Thread(target=process_csv_in_background, args=(csv_id, content, username, user_id), daemon=True).start()
    return {"csv_id": csv_id, "status": "pending"}

@router.get("/csv-status/{csv_id}")
def get_csv_status(csv_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    csv_file = db.query(CSVFile).filter(CSVFile.id == csv_id).first()
    if not csv_file:
        raise HTTPException(status_code=404, detail="CSV file not found")
    return {"csv_id": csv_file.id, "status": csv_file.status}

@router.get("/csv/{csv_id}")
def get_csv_file(csv_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    csv_file = db.query(CSVFile).filter(CSVFile.id == csv_id).first()
    if not csv_file:
        raise HTTPException(status_code=404, detail="CSV file not found")
    if csv_file.status != 'done':
        raise HTTPException(status_code=400, detail="CSV file is not ready yet. Current status: {}".format(csv_file.status))
    return Response(
        content=csv_file.file_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_file.filename}"}
    )

@router.get("/csvs")
def list_csvs(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    csvs = db.query(CSVFile).filter(CSVFile.user_id == current_user.get('user_id')).all()
    result = [
        {
            "id": csv.id,
            "filename": csv.filename,
            "username": csv.username,
            "user_id": csv.user_id,
            "created_at": csv.created_at.isoformat() if csv.created_at else None
        }
        for csv in csvs
    ]
    return JSONResponse(content=result) 