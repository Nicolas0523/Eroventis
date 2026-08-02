import os
import ee
import asyncio
import uuid 
import numpy as np

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from datetime import datetime, timedelta
from cachetools import TTLCache
from collections import OrderedDict

from aiogram.types import Update
from bot.bot_instance import bot, dp
from bot.api import close_client

from schemas import AnalysisRequest, ChatRequest
from assistant import generate_individual_response
from predictor import prediction_grid, prediction_future_grid, get_feature_importance
from grid import calculate_hotspots 
from gee_service import resolve_dates

# Инициализация Earth Engine
try:
    service_account = os.getenv("GEE_SERVICE_ACCOUNT")
    private_key     = os.getenv("GEE_PRIVATE_KEY")
    credentials = ee.ServiceAccountCredentials(service_account, key_data=private_key)
    ee.Initialize(credentials)
except Exception:
    ee.Authenticate()
    ee.Initialize()

app = FastAPI(title="WindGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

climate_cache = TTLCache(maxsize=50, ttl=86400)
jobs = OrderedDict()
MAX_JOBS = 50
RESOLUTION = 10
GEE_TIMEOUT_SECONDS = 120

jobs_lock = asyncio.Lock()
analysis_semaphore = asyncio.Semaphore(2)


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}

@app.on_event("startup")
async def set_bot_webhook():
    render_url = "https://windguard-1.onrender.com"
    await bot.set_webhook(url=f"{render_url}/telegram/webhook")

async def cleanup_job(job_id):
    await asyncio.sleep(600)   
    jobs.pop(job_id, None)

async def create_job(background_tasks: BackgroundTasks, func, data):
    job_id = str(uuid.uuid4())

    async with jobs_lock:
        jobs[job_id] = {"status": "processing"}

        if len(jobs) > MAX_JOBS:
            jobs.popitem(last=False)

    background_tasks.add_task(run_job, job_id, func, data)

    return {
        "job_id": job_id,
        "status": "processing"
    }

async def run_job(job_id: str, func, data):
    async with analysis_semaphore:
        try:
            result = await asyncio.wait_for(
                run_in_threadpool(func, data),
                timeout=GEE_TIMEOUT_SECONDS
            )

            async with jobs_lock:
                if result.get("error"):
                    jobs[job_id] = {
                        "status": "error",
                        **result
                    }
                else:
                    jobs[job_id] = {
                        "status": "done",
                        **result
                    }

                if len(jobs) > MAX_JOBS:
                    jobs.popitem(last=False)

        except asyncio.TimeoutError:
            async with jobs_lock:
                jobs[job_id] = {
                    "status": "error",
                    "error": f"Analysis timeout ({GEE_TIMEOUT_SECONDS} sec)"
                }

        except Exception as e:
            import traceback
            print(traceback.format_exc())

            async with jobs_lock:
                jobs[job_id] = {
                    "status": "error",
                    "error": str(e)
                }

        finally:
            asyncio.create_task(cleanup_job(job_id))


def _calculate_weighted_risk(grid_cells):
    if not grid_cells:
        return 0.0
    risks = [p.get("risk", 0.0) for p in grid_cells if p.get("risk") is not None]
    if not risks:
        return 0.0
        
    mean_risk = sum(risks) / len(risks)
    top_90th_risk = float(np.percentile(risks, 90))
    
    return float((mean_risk * 0.6) + (top_90th_risk * 0.4))


# --- HISTORICAL ANALYSIS ---
@app.post("/analyze")
async def analyze(
    data: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    return await create_job(
        background_tasks,
        _analyze_sync,
        data
    )

def _analyze_sync(data: AnalysisRequest):
    polygon = ee.Geometry.Polygon(data.geometry.coordinates)
    resolution = RESOLUTION
        
    actual_start, actual_end, is_forecast = resolve_dates(data.start_date, data.end_date)
    try:
        grid_cells = prediction_grid(polygon, actual_start, actual_end, resolution_km=resolution)
    except Exception as e:
        return {"error": str(e)}

    if not grid_cells:
        return {"error": f"Нет данных для периода {actual_start} → {actual_end}"}

    overall_risk = _calculate_weighted_risk(grid_cells)
    hotspots = calculate_hotspots(grid_cells, risk_threshold=0.25, min_size=2)

    return {
        "polygon":     data.geometry.coordinates,
        "grid":        grid_cells,  
        "risk_score":  round(overall_risk, 4),
        "hotspots":    hotspots,  
        "feature_importances": get_feature_importance(),
        "context": {
            "risk_score": round(overall_risk, 4),
            "start_date": actual_start,
            "end_date":   actual_end,
            "forecast":   is_forecast
        }
    }


# --- 10-DAY FORECAST ---
@app.post("/analyze/short")
async def forecast_short(
    data: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    return await create_job(
        background_tasks,
        short_forecast_sync,
        data
    )

def short_forecast_sync(data: AnalysisRequest):
    polygon = ee.Geometry.Polygon(data.geometry.coordinates)
    resolution = RESOLUTION
        
    today        = datetime.now()
    actual_start = today.replace(year=today.year - 1).strftime("%Y-%m-%d")
    actual_end   = (today.replace(year=today.year - 1) + timedelta(days=30)).strftime("%Y-%m-%d")

    forecast_from = today.strftime("%Y-%m-%d")
    forecast_to   = (today + timedelta(days=10)).strftime("%Y-%m-%d")

    grid_cells = prediction_grid(polygon, actual_start, actual_end, resolution_km=resolution)

    if not grid_cells:
        return {"error": f"Нет данных для периода {actual_start} → {actual_end}"}

    overall_risk = _calculate_weighted_risk(grid_cells)
    hotspots = calculate_hotspots(grid_cells, risk_threshold=0.25, min_size=2)

    return {
        "polygon":       data.geometry.coordinates,
        "grid":          grid_cells, 
        "risk_score":    round(overall_risk, 4),
        "hotspots":      hotspots,
        "forecast_type": "10-day",
        "is_forecast":   True,
        "note":          "Forecast based on satellite baseline & trend modeling",
        "period":        f"{forecast_from} to {forecast_to}",
        "feature_importances": get_feature_importance(),
        "context": {
            "risk_score":    round(overall_risk, 4),
            "start_date":    actual_start,
            "end_date":      actual_end,
            "forecast_from": forecast_from,
            "forecast_to":   forecast_to
        }
    }


# --- 2040-2050 CLIMATE PREDICTION (SSP5-8.5) ---
@app.post("/analyze/climate")
async def forecast_climate(
    data: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    return await create_job(
        background_tasks,
        _climate_forecast_sync,
        data
    )

def _climate_forecast_sync(data: AnalysisRequest):
    polygon   = ee.Geometry.Polygon(data.geometry.coordinates)
    cache_key = f"future_{str(data.geometry.coordinates)}_{data.start_date}"

    if cache_key in climate_cache:
        return climate_cache[cache_key]

    try:
        month = int(data.start_date.split("-")[1])
    except Exception:
        month = 6  

    resolution = RESOLUTION
    grid_climate = prediction_future_grid(polygon, month=month, resolution_km=resolution)

    if not grid_climate:
        return {"error": "Failed to generate climate forecast for this region."}

    future_risk = _calculate_weighted_risk(grid_climate)

    hotspots = calculate_hotspots(grid_climate, risk_threshold=0.25, min_size=2)

    result = {
        "polygon":     data.geometry.coordinates,
        "grid":        grid_climate,
        "risk_score":  round(future_risk, 4),
        "hotspots":    hotspots,
        "scenario":    "SSP5-8.5",
        "period":      "2040-2050",
        "is_forecast": True,
        "feature_importances": get_feature_importance(),
        "context": {
            "risk_score":     round(future_risk, 4),
            "scenario":       "SSP5-8.5 (worst case)",
            "period":         "2040-2050",
            "hotspots_found": len(hotspots)
        }
    }
        
    climate_cache[cache_key] = result
    return result


@app.get("/analyze/status/{job_id}")
async def get_status(job_id: str):
    async with jobs_lock:
        job = jobs.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return job


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        response = generate_individual_response(
            user_message=req.message,
            data=req.analysis_data
        )

        return {
            "response": response
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.on_event("shutdown")
async def shutdown():
    await close_client()