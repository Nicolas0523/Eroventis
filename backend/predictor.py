import numpy as np
import pandas as pd
from datetime import datetime
from scipy.ndimage import gaussian_filter

from config import ml_model, bias_shift
from data_loader import load_raw_data, load_raw_data_multi_year
from extract_features import (
    extract_features, 
    extract_features_grid, 
    extract_future_features_grid,
    FEATURE_COLUMNS
)

# Reference AAI value computed as the 99.9th percentile
# of the training target (2018–2023).
# Used only for linear scaling of model output.
# The resulting value is a relative erosion index (0–100),
# not a probability.
AAI_REFERENCE = 1.7583


def _scale_aai_to_percent(preds):
    preds = np.asarray(preds, dtype=float)
    print("DEBUG preds before shift:", preds) # Посмотри, что выдает модель
    
    if bias_shift is not None:
        preds += bias_shift
        print("DEBUG preds after shift:", preds)
        
    preds = np.maximum(preds, 0)

    risk_percent = 100.0 * preds / AAI_REFERENCE

    return np.clip(risk_percent, 0.0, 100.0).flatten()


def smooth_grid_risks(grid_results, sigma=1.0):
    if not grid_results or not isinstance(grid_results, list) or len(grid_results) == 0:
        return []

    lats = [entry.get('lat') for entry in grid_results if isinstance(entry, dict) and 'lat' in entry]
    lons = [entry.get('lon') for entry in grid_results if isinstance(entry, dict) and 'lon' in entry]

    if not lats or not lons:
        return grid_results

    unique_lats = sorted(list(set(round(l, 5) for l in lats if l is not None)), reverse=True)
    unique_lons = sorted(list(set(round(l, 5) for l in lons if l is not None)))

    if not unique_lats or not unique_lons:
        return grid_results

    lat_map = {lat: idx for idx, lat in enumerate(unique_lats)}
    lon_map = {lon: idx for idx, lon in enumerate(unique_lons)}

    n_rows = len(unique_lats)
    n_cols = len(unique_lons)

    grid_matrix = np.zeros((n_rows, n_cols))
    weight_mask = np.zeros((n_rows, n_cols))

    for entry in grid_results:
        if not isinstance(entry, dict):
            continue
        lat_val = entry.get('lat')
        lon_val = entry.get('lon')
        if lat_val is None or lon_val is None:
            continue

        r = lat_map.get(round(lat_val, 5))
        c = lon_map.get(round(lon_val, 5))
        
        if r is not None and c is not None:
            risk_val = entry.get('risk_percent', entry.get('risk', 0.0))
            grid_matrix[r, c] = risk_val
            weight_mask[r, c] = 1.0

    smoothed_vals = gaussian_filter(grid_matrix, sigma=sigma, mode='nearest')
    smoothed_weights = gaussian_filter(weight_mask, sigma=sigma, mode='nearest')

    normalized_smoothed = np.divide(
        smoothed_vals, 
        smoothed_weights, 
        out=np.zeros_like(smoothed_vals), 
        where=smoothed_weights > 0
    )

    for entry in grid_results:
        if not isinstance(entry, dict):
            continue
        lat_val = entry.get('lat')
        lon_val = entry.get('lon')
        if lat_val is None or lon_val is None:
            continue

        r = lat_map.get(round(lat_val, 5))
        c = lon_map.get(round(lon_val, 5))

        if r is not None and c is not None:
            smoothed_val = round(float(np.clip(normalized_smoothed[r, c], 0.0, 100.0)), 1)
            entry['risk_percent'] = smoothed_val
            entry['risk'] = smoothed_val

    return grid_results


def prediction_val(polygon, start_date, end_date):
    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled_features, _ = extract_features(raw_data, polygon, month)

    raw_pred = ml_model.predict(scaled_features)
    risk_percent = _scale_aai_to_percent(raw_pred)

    if len(risk_percent) == 0:
        return 0.0

    return float(risk_percent[0])


def prediction_grid(polygon, start_date, end_date, resolution_km=10):
    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled, coords_meta = extract_features_grid(raw_data, polygon, month, resolution_km)

    if scaled is None or len(scaled) == 0 or not coords_meta:
        return []

    raw_preds = ml_model.predict(scaled)
    preds = _scale_aai_to_percent(raw_preds)

    grid_results = []
    for meta_entry, risk_val in zip(coords_meta, preds):
        if not isinstance(meta_entry, dict):
            continue
        grid_results.append({
            "i": meta_entry.get('i', 0),
            "j": meta_entry.get('j', 0),
            "lat": meta_entry.get("lat", 0.0),
            "lon": meta_entry.get("lon", 0.0),
            "risk_percent": float(risk_val),
            "ndvi": meta_entry.get("raw_ndvi", 0.15),
            "wind": meta_entry.get("raw_wind", 8.0),
            "temp": meta_entry.get("raw_temp", 25.0),
            "soil_moisture": meta_entry.get("soil_moisture", 0.2),
            "soil_type": meta_entry.get("soil_type", 2.0),
            "slope": meta_entry.get("slope", 1.0),
            "step_deg": meta_entry.get("step_deg", 0.09)
        })

    grid_results = smooth_grid_risks(grid_results, sigma=1.0)
    return grid_results


def prediction_future_grid(polygon, month, resolution_km=10):
    target_month = month if month in [5, 6, 7, 8, 9] else 7
    raw_data = load_raw_data_multi_year(polygon, "2025-06-01", "2025-08-31") 

    scaled, coords_meta = extract_future_features_grid(
        raw_data, polygon, target_month, resolution_km=resolution_km
    )

    if scaled is None or len(scaled) == 0 or not coords_meta:
        return []

    raw_preds = ml_model.predict(scaled)
    preds = _scale_aai_to_percent(raw_preds)

    grid_results = []
    for meta_entry, risk_val in zip(coords_meta, preds):
        if not isinstance(meta_entry, dict):
            continue
        grid_results.append({
            "i": meta_entry.get('i', 0),
            "j": meta_entry.get('j', 0),
            "lat": meta_entry.get("lat", 0.0),
            "lon": meta_entry.get("lon", 0.0),
            "risk_percent": float(risk_val),
            "ndvi": meta_entry.get("raw_ndvi", 0.15),
            "wind": meta_entry.get("raw_wind", 8.0),
            "temp": meta_entry.get("raw_temp", 25.0),
            "soil_moisture": meta_entry.get("soil_moisture", 0.2),
            "soil_type": meta_entry.get("soil_type", 2.0),
            "slope": meta_entry.get("slope", 1.0),
            "step_deg": meta_entry.get("step_deg", 0.09)
        })

    grid_results = smooth_grid_risks(grid_results, sigma=1.0)
    return grid_results


def get_feature_importance():
    importances = ml_model.feature_importances_
    feature_data = [
        {"name": f, "value": float(i)} 
        for f, i in zip(FEATURE_COLUMNS, importances)
    ]
    return sorted(feature_data, key=lambda x: x['value'], reverse=True)