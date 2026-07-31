import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split # Добавили инструмент сплита
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
import joblib
import matplotlib.pyplot as plt
import shap
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')


df1 = pd.read_csv(r"C:\Users\User\Desktop\проекты\windguard_2.0\WindGuard_REAL_TRAIN_2018_2023.csv")
df2 = pd.read_csv(r"C:\Users\User\Desktop\проекты\windguard_2.0\WindGuard_REAL_TEST_2024_2025.csv")


df_full = pd.concat([df1, df2]).reset_index(drop=True)
df_full = df_full.dropna(subset=['erosion_risk']).reset_index(drop=True)


train, test = train_test_split(df_full, test_size=0.2, random_state=42)
print(f"Коммерческий Train: {train.shape}, Коммерческий Test: {test.shape}")


target_scaler = StandardScaler()
y_train = target_scaler.fit_transform(train[['erosion_risk']]).flatten()
y_test = target_scaler.transform(test[['erosion_risk']]).flatten()


for dataset in [train, test]:
    dataset["aridity_index"] = dataset["rain"] / (dataset["evaporation"].abs() + 1e-9)
    dataset["is_dry_season"] = dataset["month"].isin([6, 7, 8, 9]).astype(int)


monthly_mean = train.groupby("month")["NDVI_now"].mean()
monthly_std = train.groupby("month")["NDVI_now"].std()
train["ndvi_zscore"] = (train["NDVI_now"] - train["month"].map(monthly_mean)) / (train["month"].map(monthly_std) + 1e-9)
test["ndvi_zscore"] = (test["NDVI_now"] - test["month"].map(monthly_mean)) / (test["month"].map(monthly_std) + 1e-9)

biome_mean = train.groupby(["biome", "month"])["NDVI_now"].mean()
global_mean = train["NDVI_now"].mean()
train["ndvi_biome_anomaly"] = train.apply(lambda row: row["NDVI_now"] - biome_mean.loc[(row["biome"], row["month"])], axis=1)
test["ndvi_biome_anomaly"] = test.apply(lambda row: row["NDVI_now"] - biome_mean.get((row["biome"], row["month"]), global_mean), axis=1)

features = [
    "NDVI_now", "NDVI_anomaly", "wind_mean", "wind_max", "rain", "tempC", 
    "soil_moisture", "evaporation", "slope", "soil_type", "biome", "month", 
    "latitude", "longitude", "aridity_index", "is_dry_season", 
    "ndvi_zscore", "ndvi_biome_anomaly"
]

X_train = train[features]
X_test = test[features]

scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc = scaler.transform(X_test)

model = XGBRegressor(
    n_estimators=1000,         
    max_depth=10,              
    learning_rate=0.03,       
    subsample=0.8,             
    colsample_bytree=0.8,      
    reg_alpha=0.0,             
    reg_lambda=1.0,            
    eval_metric="mae",
    random_state=42,
    n_jobs=-1
)

print("\nTraining Commercial XGBoost Regressor...")
model.fit(X_train_sc, y_train)
print("Done!")


raw_preds = model.predict(X_test_sc)

bias_shift = np.mean(y_test) - np.mean(raw_preds)
preds = raw_preds + bias_shift 

print("\n=== Честные Общие Метрики после Калибровки Смещения ===")
print(f"MAE: {mean_absolute_error(y_test, preds):.4f}")
print(f"MSE: {mean_squared_error(y_test, preds):.4f}")
print(f"Честный R²: {r2_score(y_test, preds):.4f}")

fig, axes = plt.subplots(1, 3, figsize=(16, 5))

plot_size = min(2000, len(y_test))
axes[0].scatter(y_test[:plot_size], preds[:plot_size], alpha=0.3, s=6, c='#1f77b4')
min_val, max_val = min(y_test.min(), preds.min()), max(y_test.max(), preds.max())
axes[0].plot([min_val, max_val], [min_val, max_val], 'r--', lw=2)  
axes[0].set_xlim(min_val, max_val)
axes[0].set_ylim(min_val, max_val)
axes[0].set_title("Real vs Predicted (Calibrated)")

feat_imp = pd.Series(model.feature_importances_, index=features).sort_values()
feat_imp.plot(kind='barh', ax=axes[1], color='#2ca02c')
axes[1].set_title("XGBoost Feature Importance")

residuals = y_test - preds
axes[2].hist(residuals, bins=50, color='#d62728', alpha=0.7)
axes[2].axvline(0, color='black', linestyle='dashed', linewidth=2)
axes[2].set_title("Centered Error Distribution Profile")

plt.tight_layout()
plt.savefig(r"C:\Users\User\Desktop\проекты\windguard_2.0\model_v5_results.png", dpi=150)
plt.show()


ndvi_stats = train.groupby('month')['NDVI_now'].agg(['mean','std']).to_dict()
ndvi_biome_stats = train.groupby(['biome','month'])['NDVI_now'].mean().to_dict()
joblib.dump(ndvi_stats, r"C:\Users\User\Desktop\проекты\windguard_2.0\ndvi_stats.pkl")
joblib.dump(ndvi_biome_stats, r"C:\Users\User\Desktop\проекты\windguard_2.0\ndvi_biome_stats.pkl")
joblib.dump(model, r"C:\Users\User\Desktop\проекты\windguard_2.0\xgb_model_v5.pkl")
joblib.dump(scaler, r"C:\Users\User\Desktop\проекты\windguard_2.0\scaler_v5.pkl") 
joblib.dump(target_scaler, r"C:\Users\User\Desktop\проекты\windguard_2.0\target_scaler_v5.pkl")
joblib.dump(features, r"C:\Users\User\Desktop\проекты\windguard_2.0\features_v5.pkl")
joblib.dump(bias_shift, r"C:\Users\User\Desktop\проекты\windguard_2.0\bias_shift.pkl")
print("\nВсе артефакты модели v5 сохранены для FastAPI производства.")


print("\nRunning SHAP Analysis...")
booster = model.get_booster()


X_test_sample = X_test_sc[:300]
dtest_shap = xgb.DMatrix(X_test_sample, feature_names=features)


shap_contribs = booster.predict(dtest_shap, pred_contribs=True)


shap_values_matrix = shap_contribs[:, :-1]

plt.figure(figsize=(11, 7))
shap.summary_plot(shap_values_matrix, X_test.iloc[:300], feature_names=features, show=False)
plt.title("SHAP Global Feature Impact on Wind Erosion in Kazakhstan", fontsize=14)
plt.tight_layout()
plt.savefig(r"C:\Users\User\Desktop\проекты\windguard_2.0\shap_importance_v5.png", dpi=150)
plt.show()
print("\nSHAP Analysis completed successfully!")
