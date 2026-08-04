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


def smooth_grid_risks(grid_results, sigma=0.7):
    if not grid_results:
        return []

    max_i = max(cell['i'] for cell in grid_results)
    max_j = max(cell['j'] for cell in grid_results)

    grid_matrix = np.full((max_i + 1, max_j + 1), np.nan)
    for cell in grid_results:
        grid_matrix[cell['i'], cell['j']] = cell['risk']

    nan_mask = np.isnan(grid_matrix)
    grid_matrix_filled = np.where(nan_mask, 0.0, grid_matrix)

    smoothed = gaussian_filter(grid_matrix_filled, sigma=sigma)

    for cell in grid_results:
        i, j = cell['i'], cell['j']
        if not nan_mask[i, j]:
            cell['risk'] = round(float(np.clip(smoothed[i, j], 0.0, 100.0)), 1)

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

    if len(scaled) == 0:
        return []

    raw_preds = ml_model.predict(scaled)
    preds = _apply_calibration(raw_preds)

    grid_results = []
    for cell, risk in zip(coords_meta, preds):
        grid_results.append({
            "i": cell.get('i', 0),
            "j": cell.get('j', 0),
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": float(risk),
            "ndvi": cell["raw_ndvi"],
            "wind": cell["raw_wind"],
            "temp": cell["raw_temp"],
            "soil_moisture": cell.get("soil_moisture", 0.2),
            "soil_type": cell.get("soil_type", 2.0),
            "slope": cell.get("slope", 1.0),
            "step_deg": cell["step_deg"]
        })

    return smooth_grid_risks(grid_results, sigma=0.7)


def prediction_future_grid(polygon, month, resolution_km=10):
    target_month = month if month in [5, 6, 7, 8, 9] else 7

    raw_data = load_raw_data_multi_year(polygon, "2025-06-01", "2025-08-31") 

    scaled, coords_meta = extract_future_features_grid(
        raw_data, polygon, target_month, resolution_km=resolution_km
    )

    if len(scaled) == 0:
        return []

    raw_preds = ml_model.predict(scaled)
    preds = _apply_calibration(raw_preds)

    grid_results = []
    for cell, risk in zip(coords_meta, preds):
        grid_results.append({
            "i": cell.get('i', 0),
            "j": cell.get('j', 0),
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": float(risk),
            "ndvi": cell["raw_ndvi"],
            "wind": cell["raw_wind"],
            "temp": cell["raw_temp"],
            "soil_moisture": cell.get("soil_moisture", 0.2),
            "soil_type": cell.get("soil_type", 2.0),
            "slope": cell.get("slope", 1.0),
            "step_deg": cell["step_deg"]  
        })

    return smooth_grid_risks(grid_results, sigma=0.7)


def get_feature_importance():
    importances = ml_model.feature_importances_
    feature_data = [
        {"name": f, "value": float(i)} 
        for f, i in zip(FEATURE_COLUMNS, importances)
    ]
    return sorted(feature_data, key=lambda x: x['value'], reverse=True)