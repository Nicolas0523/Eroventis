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
    if preds is None or len(preds) == 0:
        return np.array([])
    
    preds_arr = np.array(preds)
    if bias_shift is not None:
        preds_arr = preds_arr + bias_shift
        
    calibrated = 1 / (1 + np.exp(-preds_arr / 4.0)) * 100.0
    return np.clip(calibrated, 0.0, 100.0).flatten()


def smooth_grid_risks(grid_results, sigma=1.2):
    """
    Абсолютно защищенное Гауссово сглаживание.
    Исключает UnboundLocalError и ошибки обращения к пустым переменным.
    """
    if not grid_results or not isinstance(grid_results, list) or len(grid_results) == 0:
        return []

    # 1. Сбор уникальных координат через безопасные генераторы
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

    # 2. Заполнение матрицы
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
            grid_matrix[r, c] = entry.get('risk', 0.0)
            weight_mask[r, c] = 1.0

    # 3. Нормированная свёртка
    smoothed_vals = gaussian_filter(grid_matrix, sigma=sigma, mode='nearest')
    smoothed_weights = gaussian_filter(weight_mask, sigma=sigma, mode='nearest')

    normalized_smoothed = np.divide(
        smoothed_vals, 
        smoothed_weights, 
        out=np.zeros_like(smoothed_vals), 
        where=smoothed_weights > 0
    )

    # 4. Запись результатов
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
            entry['risk'] = round(float(np.clip(normalized_smoothed[r, c], 0.0, 100.0)), 1)

    return grid_results


def prediction_val(polygon, start_date, end_date):
    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled_features, _ = extract_features(raw_data, polygon, month)

    raw_pred = ml_model.predict(scaled_features)
    calibrated = _apply_calibration(raw_pred)

    if len(calibrated) == 0:
        return 0.0

    return float(calibrated[0])


def prediction_grid(polygon, start_date, end_date, resolution_km=10):
    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled, coords_meta = extract_features_grid(raw_data, polygon, month, resolution_km)

    if scaled is None or len(scaled) == 0 or not coords_meta:
        return []

    raw_preds = ml_model.predict(scaled)
    preds = _apply_calibration(raw_preds)

    grid_results = []
    for meta_entry, risk_val in zip(coords_meta, preds):
        if not isinstance(meta_entry, dict):
            continue
        grid_results.append({
            "i": meta_entry.get('i', 0),
            "j": meta_entry.get('j', 0),
            "lat": meta_entry.get("lat", 0.0),
            "lon": meta_entry.get("lon", 0.0),
            "risk": float(risk_val),
            "ndvi": meta_entry.get("raw_ndvi", 0.15),
            "wind": meta_entry.get("raw_wind", 8.0),
            "temp": meta_entry.get("raw_temp", 25.0),
            "soil_moisture": meta_entry.get("soil_moisture", 0.2),
            "soil_type": meta_entry.get("soil_type", 2.0),
            "slope": meta_entry.get("slope", 1.0),
            "step_deg": meta_entry.get("step_deg", 0.09)
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
    for meta_entry, risk_val in zip(coords_meta, preds):
        if not isinstance(meta_entry, dict):
            continue
        grid_results.append({
            "i": meta_entry.get('i', 0),
            "j": meta_entry.get('j', 0),
            "lat": meta_entry.get("lat", 0.0),
            "lon": meta_entry.get("lon", 0.0),
            "risk": float(risk_val),
            "ndvi": meta_entry.get("raw_ndvi", 0.15),
            "wind": meta_entry.get("raw_wind", 8.0),
            "temp": meta_entry.get("raw_temp", 25.0),
            "soil_moisture": meta_entry.get("soil_moisture", 0.2),
            "soil_type": meta_entry.get("soil_type", 2.0),
            "slope": meta_entry.get("slope", 1.0),
            "step_deg": meta_entry.get("step_deg", 0.09)
        })

    return smooth_grid_risks(grid_results, sigma=1.2)


def get_feature_importance():
    importances = ml_model.feature_importances_
    feature_data = [
        {"name": f, "value": float(i)} 
        for f, i in zip(FEATURE_COLUMNS, importances)
    ]
    return sorted(feature_data, key=lambda x: x['value'], reverse=True)