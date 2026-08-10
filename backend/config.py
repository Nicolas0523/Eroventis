import ee
import os
import joblib
from dotenv import load_dotenv
from pathlib import Path


load_dotenv()

SCRIPT_DIR  = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

SCALER_PATH   = PROJECT_ROOT / "scaler_v5.pkl"
MODEL_PATH    = PROJECT_ROOT / "xgb_model_v5.pkl"
FEATURES_PATH = PROJECT_ROOT / "features_v5.pkl"
BIAS_SHIFT_PATH    = PROJECT_ROOT / "bias_shift.pkl"
BOUNDS_PATH = PROJECT_ROOT / "train_bounds.pkl"


ndvi_stats = joblib.load(SCRIPT_DIR / "ndvi_stats.pkl")
scaler   = joblib.load(SCALER_PATH)
ml_model = joblib.load(MODEL_PATH)
features = joblib.load(FEATURES_PATH)
bias_shift    = joblib.load(BIAS_SHIFT_PATH)
train_bounds = joblib.load(BOUNDS_PATH)


# Reference value of the erosion index (AAI).
# Computed as the 99.9th percentile of the training target.
# Used only for visualization by mapping model outputs
# to a relative 0–100 erosion intensity scale.
# This value does not represent probability.
AAI_REFERENCE = 1.7583

# GEE инициализация
GEE_INITIALIZED = False

try:
    service_account = os.getenv("GEE_SERVICE_ACCOUNT")
    private_key     = os.getenv("GEE_PRIVATE_KEY")

    if service_account and private_key:
        credentials = ee.ServiceAccountCredentials(
            service_account, key_data=private_key
        )
        ee.Initialize(credentials)
        GEE_INITIALIZED = True
    else:
        pass

except Exception as e:
    print(f"GEE init failed: {e}")