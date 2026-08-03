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

# ОЧИЩЕННЫЙ СПИСОК ФИЧ v5 СТРОГО ИЗ 18 ЭЛЕМЕНТОВ
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


def extract_future_features_grid(raw_data, polygon, month, resolution_km=10):

    polygon_coords = polygon.coordinates().getInfo()[0]
    
    grid_cells = create_grid(polygon_coords, resolution_km=resolution_km)
    if not grid_cells:
        return [], []

    try:
        cmip_coll = ee.ImageCollection("NASA/GDDP-CMIP6") \
            .filterBounds(polygon) \
            .filter(ee.Filter.eq('scenario', 'ssp585')) \
            .filter(ee.Filter.calendarRange(2041, 2060, "year")) \
            .filter(ee.Filter.calendarRange(month, month, "month"))

        def normalize_cmip_bands(img):
            t = img.select('tas').resample('bilinear').subtract(273.15).rename('tempC')
            p = img.select('pr').resample('bilinear').multiply(86400).rename('rain')
            w = img.select('sfcWind').resample('bilinear').rename('wind_mean')
            
            hurs = ee.Algorithms.If(
                img.bandNames().contains('hurs'),
                img.select('hurs').resample('bilinear').divide(100.0),
                raw_data.get("soil_moisture", ee.Image.constant(0.12))
            )
            hurs_img = ee.Image(hurs).rename('soil_moisture')
            
            return ee.Image.cat([t, p, w, hurs_img])

        cmip = cmip_coll.map(normalize_cmip_bands).mean()

        tempC_future = cmip.select('tempC')
        rain_future = cmip.select('rain')
        wind_future = cmip.select('wind_mean')
        moisture_future = cmip.select('soil_moisture')

    except Exception as e:
        print(f"[CMIP6 Fallback - Using Real Data]: {e}")
        tempC_future = raw_data.get("tempC", ee.Image.constant(30.0))
        rain_future = raw_data.get("rain", ee.Image.constant(1.0))
        wind_future = raw_data.get("wind_mean", ee.Image.constant(5.0))
        moisture_future = raw_data.get("soil_moisture", ee.Image.constant(0.2))

    ndvi_future = raw_data["ndvi"].resample("bilinear").rename("NDVI_now").unmask(0.20)

    wind_max = wind_future.rename("wind_max")

    real_slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003")).rename('slope')
    real_soil  = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0').rename('soil_type')

    evaporation_future = raw_data.get("evaporation", ee.Image.constant(5.5)).rename("evaporation")

    stacked = ee.Image.cat([
        ndvi_future,
        wind_future.unmask(5.0),
        wind_max.unmask(10.0),
        rain_future.unmask(0.5),
        tempC_future.unmask(35.0),
        moisture_future.unmask(0.15),
        evaporation_future.unmask(5.5),
        real_slope.unmask(1.0),
        real_soil.unmask(2.0),
        raw_data.get("biome", ee.Image.constant(3.0)).unmask(3.0).rename("biome")
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
        geometry = f.get("geometry", {})
        coords = geometry.get("coordinates", [[[0, 0]]])[0]
        latitude  = props.get("center_lat") or (sum(pt[1] for pt in coords) / len(coords) if coords else 0)
        longitude = props.get("center_lon") or (sum(pt[0] for pt in coords) / len(coords) if coords else 0)
        
        row = _compute_features(
            ndvi_value        = props.get("NDVI_now") if props.get("NDVI_now") is not None else 0.20,
            wind_mean_value   = props.get("wind_mean") if props.get("wind_mean") is not None else 6.0,
            wind_max_value    = props.get("wind_max") if props.get("wind_max") is not None else 10.0,
            rain_value        = props.get("rain") if props.get("rain") is not None else 0.1,
            tempC_value       = props.get("tempC") if props.get("tempC") is not None else 36.5,
            moisture_value    = props.get("soil_moisture") if props.get("soil_moisture") is not None else 0.1,
            evaporation_value = props.get("evaporation") if props.get("evaporation") is not None else 7.0,
            slope_value       = props.get("slope") if props.get("slope") is not None else 1.0,
            soil_type_value   = props.get("soil_type") if props.get("soil_type") is not None else 2.0,
            biome_value       = props.get("biome") if props.get("biome") is not None else 3.0,
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
            "raw_ndvi": props.get("NDVI_now") if props.get("NDVI_now") is not None else 0.20,
            "raw_wind": props.get("wind_mean") if props.get("wind_mean") is not None else 6.0,
            "raw_temp": props.get("tempC") if props.get("tempC") is not None else 36.5
        })

    if not rows:
        return [], []
    
    df = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    return scaler.transform(df), grid_meta