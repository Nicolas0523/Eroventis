import numpy as np
import pandas as pd

train_df = pd.read_csv(r"C:\Users\User\Desktop\проекты\windguard_2.0\WindGuard_REAL_TRAIN_2018_2023.csv")
AAI_REFERENCE = train_df["erosion_risk"].quantile(0.999)


print(f"Есептелген ғылыми AAI_REFERENCE: {AAI_REFERENCE:.2f}")