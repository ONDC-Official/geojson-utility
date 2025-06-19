from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response
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
            if resp.status != 200:
                logger.error(f"HTTP {resp.status}: {body.decode()}")
                raise http.client.HTTPException(f"Unexpected status {resp.status}")
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
async def bulk_process_catchments(file: UploadFile = File(...), current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="CSV file is empty.")
        username = current_user.get('username')
        user_id = current_user.get('user_id') if 'user_id' in current_user else None
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        required_columns = {'seller_id', 'provider_id', 'lat', 'long'}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing_columns)}")
        errors = []
        geojson_results = []
        api_key = os.environ.get("LEPTON_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Lepton Maps API key not set in environment variable LEPTON_API_KEY")
        client = LeptonMapsClient(api_key=api_key)
        for idx, row in df.iterrows():
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
                    geojson = client.get_catchment_geojson(latitude=lat, longitude=lon)
                    polygon_geojson = client.extract_polygon_geojson(geojson)
                    geojson_str = json.dumps(polygon_geojson)
                except Exception as e:
                    logger.error(f"GeoJSON error for row {idx+1}: {str(e)}")
                    row_errors.append(f"GeoJSON error: {str(e)}")
            geojson_results.append(geojson_str)
            if row_errors:
                errors.append(f"Row {idx+1}: {'; '.join(row_errors)}")
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))
        df['geojson'] = geojson_results
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        processed_content = output.getvalue().encode('utf-8')
        new_csv = CSVFile(filename=file.filename, file_content=processed_content, username=username, user_id=user_id)
        db.add(new_csv)
        db.commit()
        response = StreamingResponse(
            io.BytesIO(processed_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=catchment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
        return response
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file is empty or invalid")
    except pd.errors.ParserError as e:
        raise HTTPException(status_code=400, detail=f"Error parsing CSV: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        error_message = f"Error processing file: {str(e)}"
        if 'errors' in locals() and errors:
            error_message += f"; Row errors: {'; '.join(errors)}"
        raise HTTPException(status_code=500, detail=error_message)

@router.get("/csv/{csv_id}")
def get_csv_file(csv_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    csv_file = db.query(CSVFile).filter(CSVFile.id == csv_id).first()
    if not csv_file:
        raise HTTPException(status_code=404, detail="CSV file not found")
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