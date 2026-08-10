import pandas as pd
import joblib

TRAIN_CSV = r"C:\Users\User\Desktop\проекты\windguard_2.0\WindGuard_REAL_TRAIN_2018_2023.csv"
TEST_CSV  = r"C:\Users\User\Desktop\проекты\windguard_2.0\WindGuard_REAL_TEST_2024_2025.csv"

df1 = pd.read_csv(TRAIN_CSV)
df2 = pd.read_csv(TEST_CSV)
df_full = pd.concat([df1, df2]).reset_index(drop=True)
df_full = df_full.dropna(subset=["erosion_risk"]).reset_index(drop=True)

CLIP_FEATURES = ["tempC", "wind_mean", "wind_max", "rain", "NDVI_now",
                  "soil_moisture", "evaporation"]

bounds = {
    f: (float(df_full[f].min()), float(df_full[f].max()))
    for f in CLIP_FEATURES
}

joblib.dump(bounds, r"C:\Users\User\Desktop\проекты\windguard_2.0\train_bounds.pkl")
print("Сохранено:", bounds)