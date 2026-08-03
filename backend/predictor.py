from extract_features import extract_features, extract_features_grid, extract_future_features_grid
from data_loader import load_raw_data, load_raw_data_multi_year
from config import ml_model, bias_shift
from datetime import datetime
import numpy as np


def _apply_calibration(preds):
    """Калибрует сырые предсказания модели в честные проценты от 0 до 100."""
    preds = np.array(preds)
    
    if bias_shift is not None:
        preds = preds + bias_shift
        
    # Смягченная сигмоида для плавного распределения от 0 до 100%
    calibrated = 1 / (1 + np.exp(-preds / 4.0)) * 100.0
        
    return np.clip(calibrated, 0.0, 100.0).flatten()


def prediction_val(polygon, start_date, end_date):
    raw_data = load_raw_data_multi_year(
        polygon,
        start_date,
        end_date
    )

    month = datetime.strptime(
        start_date,
        "%Y-%m-%d"
    ).month

    scaled_features, _ = extract_features(
        raw_data,
        polygon,
        month
    )

    raw_pred = ml_model.predict(scaled_features)
    calibrated = _apply_calibration(raw_pred)[0]

    return float(calibrated)


def prediction_grid(polygon, start_date, end_date, resolution_km=10):
    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled, coords_meta = extract_features_grid(raw_data, polygon, month, resolution_km)

    if len(scaled) == 0: return []

    raw_preds = ml_model.predict(scaled)
    preds = _apply_calibration(raw_preds)

    grid_results = []
    for cell, risk in zip(coords_meta, preds):
        grid_results.append({
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": float(risk),
            "ndvi": cell["raw_ndvi"],
            "wind": cell["raw_wind"],
            "temp": cell["raw_temp"],
        })

    return grid_results


def prediction_future_grid(polygon, month, resolution_km=10):
    raw_data = load_raw_data_multi_year(polygon, "2025-06-01", "2025-08-31") 

    scaled, coords_meta = extract_future_features_grid(
        raw_data, polygon, month, resolution_km=resolution_km
    )

    if len(scaled) == 0:
        return []

    # Чистое предсказание модели на основе климатических сдвигов без искусственных накруток
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
            "step_deg": cell["step_deg"]  
        })

    return grid_results


def get_feature_importance():
    features = [
        "NDVI_now", "NDVI_anomaly", "wind_mean", "wind_max", "rain", "tempC", 
        "soil_moisture", "evaporation", "slope", "soil_type", "biome", "month", 
        "latitude", "longitude", "aridity_index", "is_dry_season", 
        "ndvi_zscore", "ndvi_biome_anomaly"
    ]
    
    importances = ml_model.feature_importances_
    
    feature_data = [
        {"name": f, "value": float(i)} 
        for f, i in zip(features, importances)
    ]
    
    return sorted(feature_data, key=lambda x: x['value'], reverse=True)