import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
import joblib
import matplotlib.pyplot as plt
import shap
import xgboost as xgb
import warnings
from shapely.geometry import Point, Polygon

warnings.filterwarnings('ignore')


df1 = pd.read_csv(r"C:\Users\Nurasyl\eroventis\Eroventis\WindGuard_REAL_TRAIN_2018_2023.csv")
df2 = pd.read_csv(r"C:\Users\Nurasyl\eroventis\Eroventis\WindGuard_REAL_TEST_2024_2025.csv")

train = df1.dropna(subset=['erosion_risk']).reset_index(drop=True)
test = df2.dropna(subset=['erosion_risk']).reset_index(drop=True)

train = train.sort_values("year") if "year" in train.columns else train  
mask = ((train["year"] == 2021) & (train["month"] >= 7)) | (train["year"].isin([2022, 2023]))
train_fit_full = train[mask].copy()

val = train_fit_full[train_fit_full["year"] == 2023].copy()
train_fit = train_fit_full[train_fit_full["year"] != 2023].copy()

print(f"Коммерческий Train: {train_fit.shape}, Коммерческий Test: {test.shape}")

recent = pd.concat([df1, df2])
recent["ym"] = recent["year"].astype(str) + "-" + recent["month"].astype(str).str.zfill(2)
print(recent[(recent["year"]>=2020)&(recent["year"]<=2022)].groupby("ym")["erosion_risk"].mean())

y_train = train_fit['erosion_risk'].values
y_test = test['erosion_risk'].values


for dataset in [train_fit, val, test]:
    dataset["aridity_index"] = dataset["rain"] / (dataset["evaporation"].abs() + 1e-9)
    dataset["is_dry_season"] = dataset["month"].isin([6, 7, 8, 9]).astype(int)

monthly_mean = train_fit.groupby("month")["NDVI_now"].mean()
monthly_std = train_fit.groupby("month")["NDVI_now"].std()
biome_mean = train_fit.groupby(["biome", "month"])["NDVI_now"].mean()
global_mean = train_fit["NDVI_now"].mean()

for dataset in [train_fit, val, test]:
    dataset["ndvi_zscore"] = (dataset["NDVI_now"] - dataset["month"].map(monthly_mean)) / (dataset["month"].map(monthly_std) + 1e-9)
    dataset["ndvi_biome_anomaly"] = dataset.apply(
        lambda row: row["NDVI_now"] - biome_mean.get((row["biome"], row["month"]), global_mean), axis=1
    )

features = [
    "NDVI_now", "NDVI_anomaly", "wind_mean", "wind_max", "rain", "tempC",
    "soil_moisture", "evaporation", "slope", "soil_type", "biome", "month",
    "latitude", "longitude", "aridity_index", "is_dry_season",
    "ndvi_zscore", "ndvi_biome_anomaly"
]

X_train_fit = train_fit[features]
X_val = val[features]
X_test = test[features]
y_train_fit = train_fit["erosion_risk"].values
y_val = val["erosion_risk"].values
y_test = test["erosion_risk"].values

scaler = StandardScaler()
X_train_fit_sc = scaler.fit_transform(X_train_fit)
X_val_sc = scaler.transform(X_val)
X_test_sc = scaler.transform(X_test)

model = XGBRegressor(
    n_estimators=2000,
    max_depth=5,
    learning_rate=0.03,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.5,       # было 0.0
    reg_lambda=2.0,      # было 1.0
    eval_metric="mae",
    random_state=42,
    n_jobs=-1,
    early_stopping_rounds=50
)

model.fit(X_train_fit_sc, y_train_fit, eval_set=[(X_val_sc, y_val)], verbose=False)


raw_preds = model.predict(X_test_sc)
print(raw_preds.min(), raw_preds.mean(), raw_preds.max())

preds = raw_preds

print("\n=== Честные Общие Метрики ===")
print(f"MAE: {mean_absolute_error(y_test, preds):.4f}")
print(f"MSE: {mean_squared_error(y_test, preds):.4f}")
print(f"Честный R²: {r2_score(y_test, preds):.4f}")

print(df1.groupby("year")["erosion_risk"].agg(["mean", "std", "count"]))
print(df2.groupby("year")["erosion_risk"].agg(["mean", "std", "count"]))


test_with_preds = test.copy()
test_with_preds["prediction"] = preds
test_with_preds["residual"] = y_test - preds         
test_with_preds["abs_error"] = np.abs(y_test - preds)  

# ---------- График 1: абсолютная ошибка по координатам ----------
plt.figure(figsize=(10, 8))
sc = plt.scatter(
    test_with_preds["longitude"],
    test_with_preds["latitude"],
    c=test_with_preds["abs_error"],
    cmap="Reds",
    s=4,
    alpha=0.7
)
plt.colorbar(sc, label="Absolute Error (AAI)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.title("WindGuard v5 — Spatial Distribution of Absolute Error")
plt.tight_layout()
plt.savefig(r"C:\Users\Nurasyl\eroventis\Eroventis\residual_map_abs_error_v5.png", dpi=150)
plt.show()
 
# ---------- График 2: знаковая ошибка (недооценка / переоценка по регионам) ----------
plt.figure(figsize=(10, 8))
sc2 = plt.scatter(
    test_with_preds["longitude"],
    test_with_preds["latitude"],
    c=test_with_preds["residual"],
    cmap="RdBu_r",   # синий = модель занижает, красный = завышает
    s=4,
    alpha=0.7,
    vmin=-np.abs(test_with_preds["residual"]).max(),
    vmax=np.abs(test_with_preds["residual"]).max()
)
plt.colorbar(sc2, label="Residual (Actual - Predicted)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.title("WindGuard v5 — Spatial Bias (Blue=Underestimate, Red=Overestimate)")
plt.tight_layout()
plt.savefig(r"C:\Users\Nurasyl\eroventis\Eroventis\residual_map_signed_bias_v5.png", dpi=150)
plt.show()
 

test_with_preds["lat_bin"] = (test_with_preds["latitude"] // 0.5) * 0.5
test_with_preds["lon_bin"] = (test_with_preds["longitude"] // 0.5) * 0.5
 
grid_error_stats = test_with_preds.groupby(["lat_bin", "lon_bin"])["abs_error"].agg(["mean", "count"])
grid_error_stats = grid_error_stats[grid_error_stats["count"] >= 5] 

overall_mean_error = test_with_preds["abs_error"].mean()
worst_cells = grid_error_stats.sort_values("mean", ascending=False).head(10)


kyzylorda_poly = Polygon([
    [58.9946848551206, 45.40489634250059],
    [58.9946848551206, 46.11007417121826],
    [61.3897043863706, 47.86356286422286],
    [61.9170481363706, 47.86356286422286],
    [67.1685129801206, 46.15575451444376],
    [67.7837473551206, 43.21987424170167],
    [66.0698801676206, 42.300355167844174],
    [64.9053293863706, 43.79358602501247],
    [61.9829661051206, 43.507411740403036],
    [58.9946848551206, 45.40489634250059]
])

kyzylorda_mask = test_with_preds.apply(
    lambda row: kyzylorda_poly.contains(Point(row["longitude"], row["latitude"])), axis=1
)
 
worst_region_mask = (
    (test_with_preds["lat_bin"].isin([45.5, 40.5, 43.0, 44.0, 42.0, 44.5, 43.5]))
)
print("\n=== Проверка ошибок в Кызылординской области ===")
print(test_with_preds.loc[kyzylorda_mask, "erosion_risk"].describe())
print(test_with_preds["erosion_risk"].describe())  # для сравнения со всем датасетом

kyz = test_with_preds[kyzylorda_mask]
print(f"N наблюдений: {len(kyz)}")
print(f"MAE в Кызылорде: {kyz['abs_error'].mean():.4f}")
print(f"R² в Кызылорде: {r2_score(kyz['erosion_risk'], kyz['prediction']):.4f}")
print(f"Для сравнения — MAE по всему test: {test_with_preds['abs_error'].mean():.4f}")

print("\n=== Проверка пространственной кластеризации ошибки ===")
print(f"Средняя ошибка по всему test-сету: {overall_mean_error:.4f}")
print(f"\nТоп-10 клеток (0.5° x 0.5°) с наибольшей средней ошибкой:")
print(worst_cells)
print(
    f"\nЕсли ошибка в худших клетках заметно (>2-3x) выше средней — "
    f"это сигнал возможной пространственной кластеризации ошибок "
    f"(косвенный признак spatial leakage или систематической проблемы данных "
    f"в конкретном регионе). Если разброс некритичный — ошибка распределена "
    f"относительно равномерно."
)

# 4. Сохранение артефактов (target_scaler больше не нужен, но сохраним пустой или уберем из бэкенда)
ndvi_stats = train_fit.groupby('month')['NDVI_now'].agg(['mean','std']).to_dict()
ndvi_biome_stats = train_fit.groupby(['biome','month'])['NDVI_now'].mean().to_dict()

joblib.dump(ndvi_stats, r"C:\Users\Nurasyl\eroventis\Eroventis\ndvi_stats.pkl")
joblib.dump(ndvi_biome_stats, r"C:\Users\Nurasyl\eroventis\Eroventis\ndvi_biome_stats.pkl")
joblib.dump(model, r"C:\Users\Nurasyl\eroventis\Eroventis\xgb_model_v5.pkl")
joblib.dump(scaler, r"C:\Users\Nurasyl\eroventis\Eroventis\scaler_v5.pkl") 
joblib.dump(features, r"C:\Users\Nurasyl\eroventis\Eroventis\features_v5.pkl")
print("\nВсе артефакты модели v5 успешно обновлены и сохранены!")


print("\nRunning SHAP Analysis...")
booster = model.get_booster()


idx = np.random.RandomState(42).choice(len(X_test_sc), size=300, replace=False)
X_test_sample = X_test_sc[idx]
dtest_shap = xgb.DMatrix(X_test_sample, feature_names=features)


shap_contribs = booster.predict(dtest_shap, pred_contribs=True)


shap_values_matrix = shap_contribs[:, :-1]

plt.figure(figsize=(11, 7))
shap.summary_plot(shap_values_matrix, X_test.iloc[:300], feature_names=features, show=False)
plt.title("SHAP Global Feature Impact on Wind Erosion in Kazakhstan", fontsize=14)
plt.tight_layout()
plt.savefig(r"C:\Users\Nurasyl\eroventis\Eroventis\shap_importance_v5.png", dpi=150)
plt.show()
print("\nSHAP Analysis completed successfully!")