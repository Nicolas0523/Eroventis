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


def _apply_calibration(preds):
    preds = np.array(preds)
    if bias_shift is not None:
        preds = preds + bias_shift
        
    calibrated = 1 / (1 + np.exp(-preds / 4.0)) * 100.0
    return np.clip(calibrated, 0.0, 100.0).flatten()


def smooth_grid_risks(grid_results, sigma=1.2):
    if not grid_results or len(grid_results) == 0:
        return []

    unique_lats = sorted(list(set(round(item['lat'], 5) for item in grid_results)), reverse=True)
    unique_lons = sorted(list(set(round(item['lon'], 5))))

    if not unique_lats or not unique_lons:
        return grid_results

    lat_map = {lat: idx for idx, lat in enumerate(unique_lats)}
    lon_map = {lon: idx for idx, lon in enumerate(unique_lons)}

    n_rows = len(unique_lats)
    n_cols = len(unique_lons)

    grid_matrix = np.zeros((n_rows, n_cols))
    weight_mask = np.zeros((n_rows, n_cols))

    for item in grid_results:
        r = lat_map[round(item['lat'], 5)]
        c = lon_map[round(item['lon'], 5)]
        grid_matrix[r, c] = item['risk']
        weight_mask[r, c] = 1.0

    smoothed_vals = gaussian_filter(grid_matrix, sigma=sigma, mode='nearest')
    smoothed_weights = gaussian_filter(weight_mask, sigma=sigma, mode='nearest')

    normalized_smoothed = np.divide(
        smoothed_vals, 
        smoothed_weights, 
        out=np.zeros_like(smoothed_vals), 
        where=smoothed_weights > 0
    )

    for item in grid_results:
        r = lat_map[round(item['lat'], 5)]
        c = lon_map[round(item['lon'], 5)]
        item['risk'] = round(float(np.clip(normalized_smoothed[r, c], 0.0, 100.0)), 1)

    return grid_results


def prediction_val(polygon, start_date, end_date):
    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled_features, _ = extract_features(raw_data, polygon, month)

    raw_pred = ml_model.predict(scaled_features)
    calibrated = _apply_calibration(raw_pred)[0]

    return float(calibrated)


def prediction_grid(polygon, start_date, end_date, resolution_km=10):
    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled, coords_meta = extract_features_grid(raw_data, polygon, month, resolution_km)

    if scaled is None or len(scaled) == 0 or not coords_meta:
        return []

    raw_preds = ml_model.predict(scaled)
    preds = _apply_calibration(raw_preds)

    grid_results = []
    for meta_item, risk in zip(coords_meta, preds):
        grid_results.append({
            "i": meta_item.get('i', 0),
            "j": meta_item.get('j', 0),
            "lat": meta_item["lat"],
            "lon": meta_item["lon"],
            "risk": float(risk),
            "ndvi": meta_item["raw_ndvi"],
            "wind": meta_item["raw_wind"],
            "temp": meta_item["raw_temp"],
            "soil_moisture": meta_item.get("soil_moisture", 0.2),
            "soil_type": meta_item.get("soil_type", 2.0),
            "slope": meta_item.get("slope", 1.0),
            "step_deg": meta_item["step_deg"]
        })

    return smooth_grid_risks(grid_results, sigma=1.2)


def prediction_future_grid(polygon, month, resolution_km=10):
    target_month = month if month in [5, 6, 7, 8, 9] else 7
    raw_data = load_raw_data_multi_year(polygon, "2025-06-01", "2025-08-31") 

    scaled, coords_meta = extract_future_features_grid(
        raw_data, polygon, target_month, resolution_km=resolution_km
    )

    if scaled is None or len(scaled) == 0 or not coords_meta:
        return []

    raw_preds = ml_model.predict(scaled)
    preds = _apply_calibration(raw_preds)

    grid_results = []
    for meta_item, risk in zip(coords_meta, preds):
        grid_results.append({
            "i": meta_item.get('i', 0),
            "j": meta_item.get('j', 0),
            "lat": meta_item["lat"],
            "lon": meta_item["lon"],
            "risk": float(risk),
            "ndvi": meta_item["raw_ndvi"],
            "wind": meta_item["raw_wind"],
            "temp": meta_item["raw_temp"],
            "soil_moisture": meta_item.get("soil_moisture", 0.2),
            "soil_type": meta_item.get("soil_type", 2.0),
            "slope": meta_item.get("slope", 1.0),
            "step_deg": meta_item["step_deg"]  
        })

    return smooth_grid_risks(grid_results, sigma=1.2)


def get_feature_importance():
    importances = ml_model.feature_importances_
    feature_data = [
        {"name": f, "value": float(i)} 
        for f, i in zip(FEATURE_COLUMNS, importances)
    ]
    return sorted(feature_data, key=lambda x: x['value'], reverse=True)