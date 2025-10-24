import re
import pandas as pd
from typing import Optional, Union


def validate_location_gps(value: Union[str, float]) -> bool:
    """Validate GPS coordinates in 'lat,long' format with at least 4 decimals"""
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


def validate_id_field(field: str, value: str) -> Optional[str]:
    """Validate ID fields (snp_id, provider_id, location_id)
    
    Returns:
        None if valid, error message string if invalid
    """
    if not value:
        return f"{field} must be a non-empty string."
    if len(value) > 255:
        return f"{field} must be at most 255 characters."
    if not re.match(r'^[\w\.\-@]+$', value):
        return f"{field} contains invalid characters."
    if value.strip() != value:
        return f"{field} must not have leading/trailing whitespace."
    return None


def parse_int(val: Union[str, int, float]) -> Optional[int]:
    """Parse various types to int, returns None if invalid"""
    try:
        return int(str(val).strip())
    except ValueError:
        try:
            return int(float(str(val).strip()))
        except Exception:
            return None


def is_present(val: Union[str, int, float, None]) -> bool:
    """Check if a value is present (not None, not NaN, not empty string)"""
    return val is not None and not pd.isnull(val) and str(val).strip() != ''


def validate_drive_values(drive_distance, drive_time) -> tuple[bool, Optional[int], Optional[int], list[str]]:
    """Validate drive_distance and drive_time values
    
    Returns:
        Tuple of (use_drive_distance, drive_distance_val, drive_time_val, errors)
    """
    errors = []
    use_drive_distance = False
    drive_distance_val = None
    drive_time_val = None
    
    if not is_present(drive_distance) and not is_present(drive_time):
        errors.append("Either drive_distance or drive_time must be provided and non-empty.")
    else:
        if is_present(drive_distance):
            drive_distance_val = parse_int(drive_distance)
            if drive_distance_val is None:
                errors.append("drive_distance must be an integer if present.")
            elif drive_distance_val <= 0:
                errors.append("drive_distance must be a positive integer.")
            elif drive_distance_val > 100000:
                errors.append("drive_distance is unreasonably large.")
            else:
                use_drive_distance = True
        
        if not use_drive_distance and is_present(drive_time):
            drive_time_val = parse_int(drive_time)
            if drive_time_val is None:
                errors.append("drive_time must be an integer if present.")
            elif drive_time_val <= 0:
                errors.append("drive_time must be a positive integer.")
            elif drive_time_val > 10000:
                errors.append("drive_time is unreasonably large.")
    
    return use_drive_distance, drive_distance_val, drive_time_val, errors


def validate_csv_row(row) -> tuple[list[str], bool, Optional[int], Optional[int], Optional[float], Optional[float]]:
    """Validate a single CSV row and return processed values
    
    Returns:
        Tuple of (errors, use_drive_distance, drive_distance_val, drive_time_val, lat, lon)
    """
    row_errors = []
    
    # Extract and validate basic fields
    snp_id = str(row['snp_id']).strip()
    provider_id = str(row['provider_id']).strip()
    location_id = str(row['location_id']).strip()
    location_gps = str(row['location_gps']).strip()
    drive_distance = row.get('drive_distance')
    drive_time = row.get('drive_time')
    
    # Validate ID fields
    for field, value in [('snp_id', snp_id), ('provider_id', provider_id), ('location_id', location_id)]:
        err = validate_id_field(field, value)
        if err:
            row_errors.append(err)
    
    # Validate location_gps
    lat, lon = None, None
    if not validate_location_gps(location_gps):
        row_errors.append("location_gps must be a string with two comma-separated floats, each with at least 4 decimals, valid range.")
    else:
        lat_str, lon_str = [x.strip() for x in location_gps.split(',')]
        lat, lon = float(lat_str), float(lon_str)
        lat = float(f"{lat:.4f}")
        lon = float(f"{lon:.4f}")
        
        if not (-90 <= lat <= 90):
            row_errors.append("latitude in location_gps must be between -90 and 90.")
        if not (-180 <= lon <= 180):
            row_errors.append("longitude in location_gps must be between -180 and 180.")
    
    # Validate drive values
    use_drive_distance, drive_distance_val, drive_time_val, drive_errors = validate_drive_values(drive_distance, drive_time)
    row_errors.extend(drive_errors)
    
    return row_errors, use_drive_distance, drive_distance_val, drive_time_val, lat, lon