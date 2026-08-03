import joblib
import numpy as np  
from datetime import datetime
from extract_features import extract_features, extract_features_grid, extract_future_features_grid
from data_loader import load_raw_data, load_raw_data_multi_year
from config import ml_model, features, target_scaler, bias_shift


def prediction_val(polygon, start_date, end_date):
    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled_features, _ = extract_features(raw_data, polygon, month)
    raw_result = ml_model.predict(scaled_features) 

    calibrated_result = raw_result + bias_shift
    try:
        real_aerosol_risk = target_scaler.inverse_transform(calibrated_result.reshape(-1, 1))
        final_score = float(real_aerosol_risk[0][0])
    except Exception:
        final_score = float(calibrated_result[0])

    if 0.0 <= final_score <= 1.0:
        final_score *= 100.0


    final_score = float(np.clip(final_score, 0.0, 100.0))
    return round(final_score, 4)


def prediction_grid(polygon, start_date, end_date, resolution_km=10):
    bounds = polygon.bounds().getInfo()['coordinates'][0]
    lon_dist = abs(bounds[2][0] - bounds[0][0]) * 111
    lat_dist = abs(bounds[2][1] - bounds[0][1]) * 111
    approx_area = lon_dist * lat_dist


    raw_data = load_raw_data_multi_year(polygon, start_date, end_date)
    month = datetime.strptime(start_date, "%Y-%m-%d").month

    scaled, coords_meta = extract_features_grid(raw_data, polygon, month, resolution_km)

    if len(scaled) == 0: 
        return []

    raw_preds = ml_model.predict(scaled)
    calibrated_preds = raw_preds + bias_shift
    
    try:
        real_preds = target_scaler.inverse_transform(calibrated_preds.reshape(-1, 1)).flatten()
    except Exception:
        real_preds = calibrated_preds

    grid_results = []
    for cell, risk_val in zip(coords_meta, real_preds):
        if risk_val is None or np.isnan(risk_val):
            continue  

        r = float(risk_val)


        if 0.0 <= r <= 1.0:
            r *= 100.0

        r = float(np.clip(r, 0.0, 100.0))

        grid_results.append({
            "i": cell.get('i', 0),
            "j": cell.get('j', 0),
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": round(r / 100.0, 4),       
            "risk_score": round(r, 2),          
            "probability": round(r / 100.0, 4),
            "ndvi": cell.get("raw_ndvi"),
            "wind": cell.get("raw_wind"),
            "temp": cell.get("raw_temp"), 
            "step_deg": cell.get("step_deg", resolution_km / 111.0)
        })

    return grid_results


def prediction_future_grid(polygon, month, resolution_km=10):
    start_date = f"2023-{month:02d}-01"
    end_date   = f"2025-{month:02d}-28"

    raw_data = load_raw_data_multi_year(polygon, start_date, end_date) 
    scaled, coords_meta = extract_future_features_grid(raw_data, polygon, month, resolution_km=resolution_km)

    if len(scaled) == 0: 
        return []

    raw_preds = ml_model.predict(scaled)
    calibrated_preds = raw_preds + bias_shift
    
    try:
        real_preds = target_scaler.inverse_transform(calibrated_preds.reshape(-1, 1)).flatten()
    except Exception:
        real_preds = calibrated_preds

    grid_results = []
    for cell, risk_val in zip(coords_meta, real_preds):
        if risk_val is None or np.isnan(risk_val):
            continue

        r = float(risk_val)

        if 0.0 <= r <= 1.0:
            r *= 100.0

        r = float(np.clip(r, 0.0, 100.0))

        grid_results.append({
            "i": cell.get('i', 0),
            "j": cell.get('j', 0),
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": round(r / 100.0, 4),
            "risk_score": round(r, 2),
            "probability": round(r / 100.0, 4),
            "ndvi": cell.get("raw_ndvi"),
            "wind": cell.get("raw_wind"),
            "temp": cell.get("raw_temp"),
            "step_deg": cell.get("step_deg", resolution_km / 111.0)
        })

    return grid_results


def get_feature_importance():
    importances = ml_model.feature_importances_
    feature_data = [
        {"name": f, "value": float(i)} 
        for f, i in zip(features, importances)
    ]
    return sorted(feature_data, key=lambda x: x['value'], reverse=True)