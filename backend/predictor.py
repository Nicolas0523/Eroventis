from extract_features import extract_features, extract_features_grid, extract_future_features_grid
from data_loader import load_raw_data, load_raw_data_multi_year
from config import ml_model, features, target_scaler, bias_shift
from datetime import datetime


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
    real_aerosol_risk = target_scaler.inverse_transform(calibrated_result.reshape(-1, 1))

    final_score = float(real_aerosol_risk[0][0])

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

    if len(scaled) == 0: return []

    raw_preds = ml_model.predict(scaled)

    calibrated_preds = raw_preds + bias_shift
    real_preds = target_scaler.inverse_transform(calibrated_preds.reshape(-1, 1)).flatten()

    grid_results = []
    for i, (cell, risk) in enumerate(zip(coords_meta, real_preds)):
        grid_results.append({
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": float(risk), 
            "ndvi": float(cell["raw_ndvi"]), 
            "wind": float(cell["raw_wind"]),
            "temp": float(cell["raw_temp"]), 
        })

    return grid_results


def prediction_future_grid(polygon, month, resolution_km=10):
    raw_data = load_raw_data_multi_year(
        polygon, 
        "2025-06-01", 
        "2025-08-31"
    ) 

    scaled, coords_meta = extract_future_features_grid(
        raw_data, 
        polygon, 
        month, 
        resolution_km=resolution_km
    )

    if len(scaled) == 0: return []

    raw_preds = ml_model.predict(scaled)

    calibrated_preds = raw_preds + bias_shift
    real_preds = target_scaler.inverse_transform(calibrated_preds.reshape(-1, 1)).flatten()

    grid_results = []
    for cell, risk in zip(coords_meta, real_preds):
        grid_results.append({
            "i": cell.get('i', 0),
            "j": cell.get('j', 0),
            "lat": cell["lat"],
            "lon": cell["lon"],
            "risk": float(risk),
            "step_deg": cell["step_deg"]  
        })

    return grid_results


def get_feature_importance():
    importances = ml_model.feature_importances_
    
    feature_data = [
        {"name": f, "value": float(i)} 
        for f, i in zip(features, importances)
    ]
    
    return sorted(feature_data, key=lambda x: x['value'], reverse=True)