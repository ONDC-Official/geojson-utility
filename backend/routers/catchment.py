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
from core.lepton_usage import LeptonTokenService
import threading
import httpx
import re

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

    def get_catchment_geojson(self, latitude: float, longitude: float, catchment_type: str, accuracy_time_based: str = "HIGH", drive_distance: Optional[int] = None, drive_time: Optional[int] = None, departure_time: Optional[str] = None) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "catchment_type": catchment_type,
            "accuracy_time_based": accuracy_time_based
        }
        if drive_distance is not None:
            params["drive_distance"] = drive_distance
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
                raise Exception("Lepton Maps API: Unauthorized (HTTP 401). Your API key is invalid or expired.")
            if resp.status == 403:
                logger.error("HTTP 403: Forbidden - Lepton Maps API key is not allowed")
                raise Exception("Lepton Maps API: Forbidden (HTTP 403). Your API key does not have access.")
            if resp.status == 402:
                logger.error("HTTP 402: Not enough credits on Lepton Maps API")
                raise Exception("Lepton Maps API: Not enough credits (HTTP 402). Please check your API quota or upgrade your plan.")
            if resp.status != 200:
                logger.error(f"HTTP {resp.status}: {body_text}")
                raise Exception(f"Lepton Maps API: Unexpected status {resp.status}: {body_text}")
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
        geojson_polygon = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [outer_ring]
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
    SAMPLE_CSV_ROWS = {
        'snp_id': ['snp_1.com', 'snp_2.com'],
        'provider_id': ['provider1', 'provider2'],
        'location_id': ['L1', 'L2'],
        'location_gps': ['28.5065162,77.073938', '30.7135305,76.7454157'],
        'drive_distance': [500.5, ''],
        'drive_time': ['', 20.5]
    }
    sample_df = pd.DataFrame(SAMPLE_CSV_ROWS)
    sample_df.to_csv(output, index=False)
    output.seek(0)
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sample_catchment.csv"})

@router.post("/bulk")
@limiter.limit("10/minute")
async def bulk_process_catchments(request: Request, file: UploadFile = File(...), current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # File size limit (10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV file too large (max 2MB)")
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV with a valid filename")
    if not content:
        raise HTTPException(status_code=400, detail="CSV file is empty.")
    # Row count limit (1000 rows)
    try:
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
    if len(df) > 1000:
        raise HTTPException(status_code=400, detail="CSV file has too many rows (max 1000)")
    # Check for required columns
    required_columns = {'snp_id', 'provider_id', 'location_id', 'location_gps', 'drive_distance', 'drive_time'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        # Save CSV with errors column
        df['errors'] = [f"Missing columns: {', '.join(missing_columns)}"] * len(df)
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        csv_file.file_content = output.getvalue().encode('utf-8')
        csv_file.status = 'failed'
        csv_file.error = f"Missing columns: {', '.join(missing_columns)}"
        session.commit()
        return
    # Check for duplicate rows
    if df.duplicated().any():
        raise HTTPException(status_code=400, detail="CSV file contains duplicate rows.")
    # Check for duplicate location_id
    if df['location_id'].duplicated().any():
        dups = df[df['location_id'].duplicated(keep=False)]['location_id'].tolist()
        raise HTTPException(status_code=400, detail=f"CSV file contains duplicate location_id values: {set(dups)}")
    username = current_user.get('username')
    user_id = current_user.get('user_id')
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in authentication")
    
    # Get user's token status
    user_token_status = LeptonTokenService.get_token_status(user_id, db)
    csv_row_count = len(df)
    
    new_csv = CSVFile(filename=file.filename, file_content=content, username=username, user_id=user_id, status='pending')
    db.add(new_csv)
    db.commit()
    db.refresh(new_csv)
    csv_id = new_csv.id
    def process_csv_in_background(csv_id, content, username, user_id):
        session = next(get_db())
        try:
            csv_file = session.query(CSVFile).filter(CSVFile.id == csv_id).first()
            if not csv_file:
                return
            csv_file.status = 'processing'
            session.commit()
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
            errors_per_row = [''] * len(df)
            geojson_results = [None] * len(df)
            required_columns = {'snp_id', 'provider_id', 'location_id', 'location_gps', 'drive_distance', 'drive_time'}
            missing_columns = required_columns - set(df.columns)
            if missing_columns:
                # Save CSV with errors column
                df['errors'] = [f"Missing columns: {', '.join(missing_columns)}"] * len(df)
                output = io.StringIO()
                df.to_csv(output, index=False)
                output.seek(0)
                csv_file.file_content = output.getvalue().encode('utf-8')
                csv_file.status = 'failed'
                csv_file.error = f"Missing columns: {', '.join(missing_columns)}"
                session.commit()
                return
            api_key = os.environ.get("LEPTON_API_KEY")
            if not api_key:
                # Save CSV with errors column
                df['errors'] = ["LEPTON_API_KEY not set"] * len(df)
                output = io.StringIO()
                df.to_csv(output, index=False)
                output.seek(0)
                csv_file.file_content = output.getvalue().encode('utf-8')
                csv_file.status = 'failed'
                csv_file.error = "LEPTON_API_KEY not set"
                session.commit()
                return
            def validate_location_gps(value):
                if not isinstance(value, str):
                    return False
                value = value.strip()
                parts = value.split(',')
                if len(parts) != 2:
                    return False
                # Accept and ignore extra whitespace around lat/lon
                lat_str = parts[0].strip()
                lon_str = parts[1].strip()
                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                except Exception:
                    return False
                # Check for at least 4 decimals
                lat_dec = lat_str.split('.')[-1] if '.' in lat_str else ''
                lon_dec = lon_str.split('.')[-1] if '.' in lon_str else ''
                if len(lat_dec) < 4 or len(lon_dec) < 4:
                    return False
                # Check range
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    return False
                return True
            def validate_id_field(field, value):
                if not value:
                    return f"{field} must be a non-empty string."
                if len(value) > 255:
                    return f"{field} must be at most 255 characters."
                if not re.match(r'^[\w\.\-@]+$', value):
                    return f"{field} contains invalid characters."
                if value.strip() != value:
                    return f"{field} must not have leading/trailing whitespace."
                return None
            def parse_int(val):
                try:
                    return int(str(val).strip())
                except ValueError:
                    try:
                        return int(float(str(val).strip()))
                    except Exception:
                        return None
            def is_present(val):
                return val is not None and not pd.isnull(val) and str(val).strip() != ''
            def process_row(idx, row):
                row_errors = []
                snp_id = str(row['snp_id']).strip()
                provider_id = str(row['provider_id']).strip()
                location_id = str(row['location_id']).strip()
                location_gps = str(row['location_gps']).strip()
                drive_distance = row.get('drive_distance')
                drive_time = row.get('drive_time')
                # Validate id fields
                for field, value in [('snp_id', snp_id), ('provider_id', provider_id), ('location_id', location_id)]:
                    err = validate_id_field(field, value)
                    if err:
                        row_errors.append(err)
                # Validate location_gps
                if not validate_location_gps(location_gps):
                    row_errors.append("location_gps must be a string with two comma-separated floats, each with at least 4 decimals, valid range.")
                else:
                    lat_str, lon_str = [x.strip() for x in location_gps.split(',')]
                    lat, lon = float(lat_str), float(lon_str)
                    lat_str = f"{lat:.4f}"
                    lon_str = f"{lon:.4f}"
                    if not (-90 <= lat <= 90):
                        row_errors.append("latitude in location_gps must be between -90 and 90.")
                    if not (-180 <= lon <= 180):
                        row_errors.append("longitude in location_gps must be between -180 and 180.")
                use_drive_distance = False
                drive_distance_val = None
                drive_time_val = None
                if not is_present(drive_distance) and not is_present(drive_time):
                    row_errors.append("Either drive_distance or drive_time must be provided and non-empty.")
                else:
                    if is_present(drive_distance):
                        drive_distance_val = parse_int(drive_distance)
                        if drive_distance_val is None:
                            row_errors.append("drive_distance must be an integer if present.")
                        elif drive_distance_val <= 0:
                            row_errors.append("drive_distance must be a positive integer.")
                        elif drive_distance_val > 100000:
                            row_errors.append("drive_distance is unreasonably large.")
                        else:
                            use_drive_distance = True
                    if not use_drive_distance and is_present(drive_time):
                        drive_time_val = parse_int(drive_time)
                        if drive_time_val is None:
                            row_errors.append("drive_time must be an integer if present.")
                        elif drive_time_val <= 0:
                            row_errors.append("drive_time must be a positive integer.")
                        elif drive_time_val > 10000:
                            row_errors.append("drive_time is unreasonably large.")
                geojson_str = '{}'
                if not row_errors and 'lat' in locals() and 'lon' in locals():
                    # Step 1: Check if user has tokens available (non-consuming check)
                    if not LeptonTokenService.check_user_has_tokens(user_id, session):
                        row_errors.append("Your token allocation has been exhausted")
                    else:
                        try:
                            # Step 2: Make Lepton API call
                            client = LeptonMapsClient(api_key=api_key)
                            if use_drive_distance and drive_distance_val is not None:
                                geojson = client.get_catchment_geojson(latitude=lat_str, longitude=lon_str, catchment_type='DRIVE_DISTANCE', drive_distance=drive_distance_val)
                            elif drive_time_val is not None:
                                geojson = client.get_catchment_geojson(latitude=lat_str, longitude=lon_str, catchment_type='DRIVE_TIME', drive_time=drive_time_val)
                            else:
                                row_errors.append("Either drive_distance or drive_time must be provided and valid.")
                                return idx, geojson_str, row_errors
                                
                            # Step 3: API call succeeded - now consume token
                            if LeptonTokenService.consume_token_after_success(user_id, session):
                                polygon_geojson = client.extract_polygon_geojson(geojson)
                                geojson_str = json.dumps(polygon_geojson)
                            else:
                                # Race condition: tokens exhausted between check and consumption
                                row_errors.append("Your token allocation has been exhausted")
                                
                        except Exception as e:
                            # Step 4: API call failed - don't consume token
                            logger.error(f"GeoJSON error for row {idx+1}: {str(e)}")
                            
                            # Distinguish between different error types
                            error_str = str(e)
                            if "HTTP 402" in error_str or "Not enough credits" in error_str:
                                # Real Lepton API exhaustion
                                row_errors.append("Lepton Maps API: Not enough credits (HTTP 402). Please check your API quota or upgrade your plan.")
                            elif "HTTP 401" in error_str:
                                row_errors.append("Lepton Maps API: Unauthorized (HTTP 401). Your API key is invalid or expired.")
                            elif "HTTP 403" in error_str:
                                row_errors.append("Lepton Maps API: Forbidden (HTTP 403). Your API key does not have access.")
                            else:
                                row_errors.append(f"GeoJSON error: {str(e)}")
                return idx, geojson_str, row_errors
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(process_row, idx, row) for idx, row in df.iterrows()]
                for future in as_completed(futures):
                    idx, geojson_str, row_errors = future.result()
                    geojson_results[idx] = geojson_str
                    errors_per_row[idx] = '; '.join(row_errors)
            df['geojson'] = geojson_results
            df['errors'] = errors_per_row
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            processed_content = output.getvalue().encode('utf-8')
            csv_file.file_content = processed_content

            # Determine CSV status based on error types
            has_token_exhaustion = any("Your token allocation has been exhausted" in error for error in errors_per_row if error)
            has_lepton_api_credits = any("Lepton Maps API: Not enough credits" in error for error in errors_per_row if error)
            has_other_errors = any(error and "Your token allocation has been exhausted" not in error and "Lepton Maps API: Not enough credits" not in error for error in errors_per_row)
            
            if has_token_exhaustion and not has_other_errors and not has_lepton_api_credits:
                csv_file.status = 'partial'
                csv_file.error = 'Token allocation exhausted during processing'
            elif has_lepton_api_credits:
                csv_file.status = 'failed'
                csv_file.error = 'Lepton API credits exhausted'
            elif any(errors_per_row):
                csv_file.status = 'failed' 
                csv_file.error = 'Some rows failed, see errors column'
            else:
                csv_file.status = 'done'
                csv_file.error = None
            session.commit()
            webhook_url = os.getenv("WEBHOOK_URL")
            if webhook_url:
                try:
                    download_url = f"http://localhost:8000/catchment/csv/{csv_id}"
                    payload = {
                        "csv_id": csv_id,
                        "status": csv_file.status,
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
                csv_file.error = str(e)
                # Try to save whatever DataFrame is available
                try:
                    if 'df' in locals() and isinstance(df, pd.DataFrame):
                        # If geojson_results and errors_per_row exist, add them
                        if 'geojson_results' in locals() and len(geojson_results) == len(df):
                            df['geojson'] = geojson_results
                        if 'errors_per_row' in locals() and len(errors_per_row) == len(df):
                            df['errors'] = errors_per_row
                        output = io.StringIO()
                        df.to_csv(output, index=False)
                        output.seek(0)
                        csv_file.file_content = output.getvalue().encode('utf-8')
                except Exception as inner:
                    logger.error(f"Failed to save partial CSV on error: {inner}")
                session.commit()
        finally:
            session.close()
    threading.Thread(target=process_csv_in_background, args=(csv_id, content, username, user_id), daemon=True).start()
    
    return {
        "csv_id": csv_id, 
        "status": "pending",
        "token_info": {
            "available": user_token_status["remaining"],
            "total_rows": csv_row_count,
            "estimated_processed": min(user_token_status["remaining"], csv_row_count)
        }
    }

@router.get("/csv-status/{csv_id}")
def get_csv_status(csv_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    csv_file = db.query(CSVFile).filter(CSVFile.id == csv_id).first()
    if not csv_file:
        logger.info(f"Status check for CSV id={csv_id}: NOT FOUND")
        raise HTTPException(status_code=404, detail="CSV file not found")
    response = {"csv_id": csv_file.id, "status": csv_file.status}
    if csv_file.status == 'failed' and hasattr(csv_file, 'error') and csv_file.error:
        response["error"] = csv_file.error
    logger.info(f"Status check for CSV id={csv_id}: {response}")
    return response

@router.get("/csv/{csv_id}")
def get_csv_file(csv_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    csv_file = db.query(CSVFile).filter(CSVFile.id == csv_id).first()
    if not csv_file:
        raise HTTPException(status_code=404, detail="CSV file not found")
    if csv_file.status in ["pending", "processing"]:
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