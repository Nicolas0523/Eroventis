import ee
import numpy as np
import joblib
import pandas as pd
from pathlib import Path

from config import scaler
from grid import create_grid

SCRIPT_DIR        = Path(__file__).resolve().parent
ndvi_stats        = joblib.load(SCRIPT_DIR / "ndvi_stats.pkl")
ndvi_biome_stats  = joblib.load(SCRIPT_DIR / "ndvi_biome_stats.pkl")


FEATURE_COLUMNS = [
    'NDVI_now', 'NDVI_anomaly', 'wind_mean', 'wind_max', 'rain', 'tempC', 
    'soil_moisture', 'evaporation', 'slope', 'soil_type', 'biome', 
    'month', 'latitude', 'longitude', 'aridity_index', 'is_dry_season',
    'ndvi_zscore', 'ndvi_biome_anomaly'
]

def _compute_features(ndvi_value, wind_mean_value, wind_max_value,
                       rain_value, tempC_value, moisture_value,
                       evaporation_value, slope_value, soil_type_value,
                       biome_value, month, latitude, longitude):

    month_key = float(month)
    ndvi_mean = ndvi_stats['mean'].get(month_key, 0.0)
    ndvi_std  = ndvi_stats['std'].get(month_key, 1.0)

    # Расчет NDVI аномалии для синхронизации со скалером
    ndvi_anomaly_value = float(ndvi_value or 0) - ndvi_mean

    aridity_index         = float(rain_value or 0) / (abs(float(evaporation_value or 0)) + 1e-9)
    is_dry_season         = 1 if month in [6, 7, 8, 9] else 0 
    ndvi_zscore           = (float(ndvi_value or 0) - ndvi_mean) / (ndvi_std + 1e-9)

    biome_key          = (int(biome_value), month_key) if biome_value else None
    biome_mean         = ndvi_biome_stats.get(biome_key, ndvi_mean)
    ndvi_biome_anomaly = float(ndvi_value or 0) - biome_mean

    return [
        ndvi_value, ndvi_anomaly_value, wind_mean_value, wind_max_value,
        rain_value, tempC_value, moisture_value, evaporation_value, slope_value,
        soil_type_value, biome_value, int(month), latitude, longitude,
        aridity_index, is_dry_season, ndvi_zscore, ndvi_biome_anomaly
    ]


def extract_features(raw_data, polygon, month):
    stacked = ee.Image.cat([
        raw_data["ndvi"].rename("NDVI_now"),
        raw_data["wind_mean"].rename("wind_mean"),
        raw_data["wind_max"].rename("wind_max"),
        raw_data["rain"].rename("rain"),
        raw_data["tempC"].rename("tempC"),
        raw_data["soil_moisture"].rename("soil_moisture"),
        raw_data["evaporation"].rename("evaporation"),
        raw_data["slope"].rename("slope"),
        raw_data["soil_type"].rename("soil_type"),
        raw_data["biome"].rename("biome"),
    ])

    stats = stacked.reduceRegion(
        reducer=ee.Reducer.mean(), 
        geometry=polygon,
        scale=5000, 
        bestEffort=True, 
        maxPixels=1e9
    ).getInfo()

    wind_max_val = raw_data["wind_max"].reduceRegion(
        reducer=ee.Reducer.max(), geometry=polygon, scale=1000, bestEffort=True
    ).getInfo().get("wind_max", 0)

    coords = polygon.centroid(maxError=1).coordinates().getInfo()

    raw = _compute_features(
        ndvi_value        = stats.get("NDVI_now", 0),
        wind_mean_value   = stats.get("wind_mean", 0),
        wind_max_value    = wind_max_val,
        rain_value        = stats.get("rain", 0),
        tempC_value       = stats.get("tempC", 0),
        moisture_value    = stats.get("soil_moisture", 0),
        evaporation_value = stats.get("evaporation", 0),
        slope_value       = stats.get("slope", 0),
        soil_type_value   = stats.get("soil_type", 0),
        biome_value       = stats.get("biome", 0),
        month             = month,
        latitude          = coords[1],
        longitude         = coords[0],
    )

    df = pd.DataFrame([raw], columns=FEATURE_COLUMNS)
    return scaler.transform(df), coords


def extract_features_grid(raw_data, polygon, month, resolution_km=10):
    polygon_coords = polygon.coordinates().getInfo()[0]
    grid_cells = create_grid(polygon_coords, resolution_km=resolution_km)
    if not grid_cells:
        return [], []

    stacked = ee.Image.cat([
        raw_data["ndvi"].rename("NDVI_now"),
        raw_data["wind_mean"].rename("wind_mean"),
        raw_data["wind_max"].rename("wind_max"),
        raw_data["rain"].rename("rain"),
        raw_data["tempC"].rename("tempC"),
        raw_data["soil_moisture"].rename("soil_moisture"),
        raw_data["evaporation"].rename("evaporation"),
        raw_data["slope"].rename("slope"),
        raw_data["soil_type"].rename("soil_type"),
        raw_data["biome"].rename("biome")
    ])

    features_list = []
    for idx, cell in enumerate(grid_cells):
        cell_polygon = ee.Geometry.Polygon([cell["bounds"]])
        features_list.append(ee.Feature(cell_polygon, {
            "grid_idx": idx,
            "i": cell.get("i", 0),
            "j": cell.get("j", 0),
            "center_lat": cell["center_lat"],
            "center_lon": cell["center_lon"]
        }))
    
    fc = ee.FeatureCollection(features_list)
    calc_scale = max(resolution_km * 1000, 3000)
    reduced_fc = stacked.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=calc_scale)
    all_features_data = reduced_fc.getInfo()["features"]

    rows = []
    grid_meta = []

    for f in all_features_data:
        props = f.get("properties", {})
        if props.get("NDVI_now") is None:
            continue

        geometry = f.get("geometry", {})
        coords = geometry.get("coordinates", [[[0, 0]]])[0]
        latitude  = props.get("center_lat") or (sum(pt[1] for pt in coords) / len(coords) if coords else 0)
        longitude = props.get("center_lon") or (sum(pt[0] for pt in coords) / len(coords) if coords else 0)

        row = _compute_features(
            ndvi_value        = props.get("NDVI_now", 0),
            wind_mean_value   = props.get("wind_mean", 0),
            wind_max_value    = props.get("wind_max", 0),
            rain_value        = props.get("rain", 0),
            tempC_value       = props.get("tempC", 0),
            moisture_value    = props.get("soil_moisture", 0),
            evaporation_value = props.get("evaporation", 0),
            slope_value       = props.get("slope", 0),
            soil_type_value   = props.get("soil_type", 0),
            biome_value       = props.get("biome", 0),
            month             = month,
            latitude          = latitude,
            longitude         = longitude
        )
        rows.append(row)

        grid_meta.append({
            "i": props.get("i", 0),
            "j": props.get("j", 0),
            "lat": latitude,
            "lon": longitude,
            "step_deg": resolution_km / 111.0,
            "raw_ndvi": props.get("NDVI_now", 0),
            "raw_wind": props.get("wind_max", 0), 
            "raw_temp": props.get("tempC", 0)
        })

    if not rows:
        return [], []

    df = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    return scaler.transform(df), grid_meta


def extract_future_features_grid(raw_data, polygon, month, resolution_km=10):
    polygon_coords = polygon.coordinates().getInfo()[0]
    grid_cells = create_grid(polygon_coords, resolution_km=resolution_km)
    if not grid_cells:
        return [], []

    cmip = ee.ImageCollection("NASA/GDDP-CMIP6") \
            .filterBounds(polygon) \
            .filter(ee.Filter.eq('scenario', 'ssp585')) \
            .filter(ee.Filter.eq('model', 'ACCESS-CM2')) \
            .filter(ee.Filter.calendarRange(2040, 2050, "year")) \
            .filter(ee.Filter.calendarRange(month, month, "month")) \
            .mean()

    tempC_future = cmip.select('tas').subtract(273.15).rename("tempC")
    rain_future = cmip.select('pr').multiply(86400).rename("rain")
    wind_future = cmip.select('sfcWind').rename("wind_mean")
    
   
    moisture_future = cmip.select('hurs').divide(100.0).rename("soil_moisture")


    ndvi_layer = raw_data["ndvi"].unmask(0.12).rename("NDVI_now")

    stacked = ee.Image.cat([
        ndvi_layer,
        wind_future,
        raw_data["wind_max"].rename("wind_max"),
        rain_future,
        tempC_future,
        moisture_future,
        raw_data["evaporation"].rename("evaporation"),
        raw_data["slope"].rename("slope"),
        raw_data["soil_type"].rename("soil_type"),
        raw_data["biome"].rename("biome")
    ])

    features_list = []
    for idx, cell in enumerate(grid_cells):
        cell_polygon = ee.Geometry.Polygon([cell["bounds"]])
        features_list.append(ee.Feature(cell_polygon, {
            "grid_idx": idx,
            "i": cell.get("i", 0),
            "j": cell.get("j", 0),
            "center_lat": cell["center_lat"],
            "center_lon": cell["center_lon"]
        }))
    
    fc = ee.FeatureCollection(features_list)
    
  
    reduced_fc = stacked.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=10000)
    all_features_data = reduced_fc.getInfo()["features"]

    rows = []
    grid_meta = []

    for f in all_features_data:
        props = f.get("properties", {})
        

        ndvi_val = props.get("NDVI_now")
        if ndvi_val is None or ndvi_val == 0:
            ndvi_val = 0.12

        geometry = f.get("geometry", {})
        coords = geometry.get("coordinates", [[[0, 0]]])[0]
        latitude  = props.get("center_lat") or (sum(pt[1] for pt in coords) / len(coords) if coords else 0)
        longitude = props.get("center_lon") or (sum(pt[0] for pt in coords) / len(coords) if coords else 0)

        row = _compute_features(
            ndvi_value        = ndvi_val,
            wind_mean_value   = props.get("wind_mean", 5.0),
            wind_max_value    = props.get("wind_max", 10.0),
            rain_value        = props.get("rain", 0.2),
            tempC_value       = props.get("tempC", 32.0),
            moisture_value    = props.get("soil_moisture", 0.2),
            evaporation_value = props.get("evaporation", 6.0),
            slope_value       = props.get("slope", 1.0),
            soil_type_value   = props.get("soil_type", 2.0),
            biome_value       = props.get("biome", 3.0),
            month             = month,
            latitude          = latitude,
            longitude         = longitude
        )
        rows.append(row)
        
        grid_meta.append({
            "i": props.get("i", 0),
            "j": props.get("j", 0),
            "lat": latitude,
            "lon": longitude,
            "step_deg": resolution_km / 111.0,
            "raw_ndvi": ndvi_val,
            "raw_wind": props.get("wind_mean", 5.0),
            "raw_temp": props.get("tempC", 32.0)
        })
            
    if not rows:
        return [], []

    df = pd.DataFrame(rows, columns=FEATURE_COLUMNS)        
    return scaler.transform(df), grid_meta