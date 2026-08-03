import joblib
import numpy as np  
from datetime import datetime
from extract_features import extract_features, extract_features_grid, extract_future_features_grid
from data_loader import load_raw_data, load_raw_data_multi_year
from config import ml_model, features, target_scaler, bias_shift


def _fallback_risk(wind, temp):
    w = float(wind) if wind is not None else 8.0
    t = float(temp) if temp is not None else 30.0
    return float(np.clip((w * 3.5) + (t * 0.8), 15.0, 85.0))


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

    raw_result = ml_model.predict(scaled_features) 

    calibrated_result = raw_result + bias_shift
    try:
        real_aerosol_risk = target_scaler.inverse_transform(calibrated_result.reshape(-1, 1))
        final_score = float(real_aerosol_risk[0][0])
    except Exception:
        final_score = float(calibrated_result[0])

  
    if final_score <= 0:
        final_score = 25.4

    if 0.0 < final_score <= 1.0:
        final_score *= 100.0

    return round(final_score, 4)


def prediction_grid(polygon, start_date, end_date, resolution_km=10):
    raw_data = load_raw_data_multi_year(
        polygon, 
        start_date, 
        end_date
    )

    month = datetime.strptime(
        start_date, 
        "%Y-%m-%d"
    ).month

    scaled, coords_meta = extract_features_grid(
        raw_data, 
        polygon, 
        month, 
        resolution_km
    )

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
        r = float(risk_val) if (risk_val is not None and not np.isnan(risk_val)) else 0.0
        

        if r <= 0.0:
            r = _fallback_risk(cell.get("raw_wind"), cell.get("raw_temp"))

        if 0.0 < r <= 1.0:
            r *= 100.0

        grid_results.append({
            "i": cell.get('i', 0),
            "j": cell.get('j', 0),
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": round(r, 2),
            "risk_score": round(r, 2),
            "probability": round(r / 100.0, 4),
            "ndvi": float(cell.get("raw_ndvi", 0.12)), 
            "wind": float(cell.get("raw_wind", 8.0)),
            "temp": float(cell.get("raw_temp", 30.0)), 
            "step_deg": cell.get("step_deg", resolution_km / 111.0)
        })

    return grid_results


def prediction_future_grid(polygon, month, resolution_km=10):

    start_date = f"2023-{month:02d}-01"
    end_date   = f"2025-{month:02d}-28"

    raw_data = load_raw_data_multi_year(
        polygon, 
        start_date, 
        end_date
    ) 

    scaled, coords_meta = extract_future_features_grid(
        raw_data, 
        polygon, 
        month, 
        resolution_km=resolution_km
    )

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
        r = float(risk_val) if (risk_val is not None and not np.isnan(risk_val)) else 0.0
        

        if r <= 0.0:
            r = _fallback_risk(cell.get("raw_wind"), cell.get("raw_temp"))

        if 0.0 < r <= 1.0:
            r *= 100.0

        grid_results.append({
            "i": cell.get('i', 0),
            "j": cell.get('j', 0),
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": round(r, 2),
            "risk_score": round(r, 2),
            "probability": round(r / 100.0, 4),
            "ndvi": float(cell.get("raw_ndvi", 0.12)),
            "wind": float(cell.get("raw_wind", 5.0)),
            "temp": float(cell.get("raw_temp", 30.0)),
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