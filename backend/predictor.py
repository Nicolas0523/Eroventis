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

    if bias_shift is not None:
        preds += bias_shift

    preds = np.maximum(preds, 0)

    risk_percent = 100.0 * preds / AAI_REFERENCE

    return np.clip(risk_percent, 0.0, 100.0).flatten()



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

    return grid_results


def get_feature_importance():
    importances = ml_model.feature_importances_
    feature_data = [
        {"name": f, "value": float(i)} 
        for f, i in zip(FEATURE_COLUMNS, importances)
    ]
    return sorted(feature_data, key=lambda x: x['value'], reverse=True)