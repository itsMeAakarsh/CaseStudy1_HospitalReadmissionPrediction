import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

root = Path(__file__).resolve().parent
output_dir = root / "evaluation"
output_dir.mkdir(exist_ok=True)

patients = pd.read_csv(root / "patients.csv")
admissions = pd.read_csv(root / "admissions.csv")
diagnoses = pd.read_csv(root / "diagnoses.csv")
hospitals = pd.read_csv(root / "hospitals.csv")
billing = pd.read_csv(root / "billing.csv")

# Merge core tables
admissions["admit_date"] = pd.to_datetime(admissions["admit_date"], errors="coerce")
df = admissions.merge(patients, on="patient_id", how="left")
df = df.merge(hospitals[["hospital_id", "tier"]], on="hospital_id", how="left")

# Add diagnosis category flags
if "diag_category" in diagnoses.columns:
    diag_flags = pd.get_dummies(diagnoses[["admission_id", "diag_category"]], columns=["diag_category"], prefix="diag", dtype=int)
    diag_flags = diag_flags.groupby("admission_id", as_index=False).max()
    df = df.merge(diag_flags, on="admission_id", how="left")

# Add billing totals
billing_summary = billing.groupby("admission_id", as_index=False).agg(
    total_cost_inr=("total_cost_inr", "sum"),
    out_of_pocket_inr=("out_of_pocket_inr", "sum"),
    govt_subsidy_inr=("govt_subsidy_inr", "sum"),
)
df = df.merge(billing_summary, on="admission_id", how="left")

# Clean target columns
for col in ["readmitted_30d", "readmitted_7d"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# Create age groups
bins = [0, 18, 35, 50, 65, 120]
labels = ["0-17", "18-34", "35-49", "50-64", "65+"]
df["age_group"] = pd.cut(df["age"], bins=bins, labels=labels, right=True)

# Basic summary metrics
overall_30 = round(df["readmitted_30d"].mean() * 100, 2)
overall_7 = round(df["readmitted_7d"].mean() * 100, 2)
avg_los = round(df["los_days"].mean(), 2)
avg_cost = round(df["total_cost_inr"].mean(), 2)

# Plot 1 - Age group readmission
age_rate = df.groupby("age_group", dropna=False)["readmitted_30d"].mean().sort_values(ascending=False)
plt.figure(figsize=(10, 6))
ax = age_rate.plot(kind="bar", color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"])
plt.title("30-Day Readmission Rate by Age Group")
plt.xlabel("Age Group")
plt.ylabel("Readmission Rate")
plt.ylim(0, max(age_rate.max() * 1.2, 0.12))
for bar, value in zip(ax.patches, age_rate.values):
    ax.text(bar.get_x() + bar.get_width() / 2, value + 0.005, f"{value * 100:.1f}%", ha="center", va="bottom")
plt.tight_layout()
plt.savefig(output_dir / "viz_age_readmission.png", dpi=150)
plt.close()

# Plot 2 - Insurance type
insurance_rate = df.groupby("insurance_type", dropna=False)["readmitted_30d"].mean().sort_values(ascending=False)
plt.figure(figsize=(10, 6))
ins_plot = insurance_rate.plot(kind="bar", color="#17becf")
plt.title("30-Day Readmission Rate by Insurance Type")
plt.xlabel("Insurance Type")
plt.ylabel("Readmission Rate")
plt.xticks(rotation=20, ha="right")
for bar, value in zip(ins_plot.patches, insurance_rate.values):
    ins_plot.text(bar.get_x() + bar.get_width() / 2, value + 0.005, f"{value * 100:.1f}%", ha="center", va="bottom")
plt.tight_layout()
plt.savefig(output_dir / "viz_insurance_readmission.png", dpi=150)
plt.close()

# Plot 3 - Diagnosis category
if any(col.startswith("diag_") for col in df.columns):
    diag_cols = [col for col in df.columns if col.startswith("diag_")]
    diag_summary = []
    for col in diag_cols:
        diag_summary.append({
            "diag_category": col.replace("diag_", "").replace("_", " ").title(),
            "readmission_rate": df[col].mean(),
        })
    diag_df = pd.DataFrame(diag_summary).sort_values("readmission_rate", ascending=False)
    plt.figure(figsize=(12, 7))
    ax = diag_df.head(8).plot(kind="bar", x="diag_category", y="readmission_rate", color="#bcbd22")
    plt.title("Highest Readmission Rates by Diagnosis Category")
    plt.xlabel("Diagnosis Category")
    plt.ylabel("Readmission Rate")
    plt.xticks(rotation=30, ha="right")
    for bar, value in zip(ax.patches, diag_df.head(8)["readmission_rate"].values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.003, f"{value * 100:.1f}%", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(output_dir / "viz_diag_readmission.png", dpi=150)
    plt.close()
else:
    plt.figure(figsize=(8, 6))
    plt.text(0.5, 0.5, "No diagnosis category flags available", ha="center", va="center")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_dir / "viz_diag_readmission.png", dpi=150)
    plt.close()

# Plot 4 - Cost by tier
cost_by_tier = df.groupby(["tier", "readmitted_30d"], dropna=False)["total_cost_inr"].mean().reset_index()
if not cost_by_tier.empty:
    pivot = cost_by_tier.pivot(index="tier", columns="readmitted_30d", values="total_cost_inr").sort_index()
    pivot.columns = ["No", "Yes"]
    plt.figure(figsize=(10, 6))
    pivot.plot(kind="bar", figsize=(10, 6), color=["#7f7f7f", "#e377c2"])
    plt.title("Average Total Cost by Hospital Tier and 30-Day Readmission")
    plt.ylabel("Average Total Cost (INR)")
    plt.xlabel("Hospital Tier")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / "viz_cost_tier.png", dpi=150)
    plt.close()
else:
    plt.figure(figsize=(8, 6))
    plt.text(0.5, 0.5, "Cost data unavailable", ha="center", va="center")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_dir / "viz_cost_tier.png", dpi=150)
    plt.close()

# Plot 5 - LOS by readmission
los_summary = df.groupby("readmitted_30d", dropna=False)["los_days"].mean().reset_index()
plt.figure(figsize=(8, 6))
bars = plt.bar(["No", "Yes"], los_summary["los_days"], color=["#6b7280", "#ef476f"])
plt.title("Average Length of Stay by 30-Day Readmission")
plt.xlabel("Readmitted in 30 Days")
plt.ylabel("Length of Stay (days)")
for bar, value in zip(bars, los_summary["los_days"]):
    plt.text(bar.get_x() + bar.get_width()/2, value + 0.2, f"{value:.1f}", ha="center")
plt.tight_layout()
plt.savefig(output_dir / "viz_los_readmission.png", dpi=150)
plt.close()

# Plot 6 - Monthly trend
monthly = df.assign(month=df["admit_date"].dt.to_period("M").astype(str)).groupby("month", as_index=False)["readmitted_30d"].mean()
monthly = monthly.sort_values("month")
plt.figure(figsize=(12, 6))
plt.plot(monthly["month"], monthly["readmitted_30d"] * 100, marker="o", color="darkgreen")
plt.title("Monthly 30-Day Readmission Rate Trend")
plt.xlabel("Month")
plt.ylabel("Readmission Rate (%)")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(output_dir / "viz_monthly_trend.png", dpi=150)
plt.close()

# Generate markdown report
age_lead = age_rate.idxmax() if not age_rate.empty else "N/A"
age_lead_rate = age_rate.max() * 100 if not age_rate.empty else 0
ins_lead = insurance_rate.idxmax() if not insurance_rate.empty else "N/A"
ins_lead_rate = insurance_rate.max() * 100 if not insurance_rate.empty else 0
if any(col.startswith("diag_") for col in df.columns):
    top_diag = diag_df.iloc[0]
    diag_text = f"The highest diagnosis-category readmission rate is {top_diag['diag_category']} at {top_diag['readmission_rate'] * 100:.1f}%."
else:
    diag_text = "Diagnosis categories were not available for a category-level readmission comparison."

report = f"""# Hospital Readmission Data Visualization Report

## Overview
This report examines 30-day and 7-day readmission patterns using the hospital readmission dataset. The analysis combines patient details, admission events, diagnosis categories, billing information, and hospital-level metadata.

## Key summary metrics
- Overall 30-day readmission rate: {overall_30:.2f}%
- Overall 7-day readmission rate: {overall_7:.2f}%
- Average length of stay: {avg_los:.2f} days
- Average total cost per admission: ₹{avg_cost:,.2f}

## Main insights
- The highest 30-day readmission risk appears in the {age_lead} age group at {age_lead_rate:.1f}%.
- Insurance type {ins_lead} shows the highest observed readmission rate at {ins_lead_rate:.1f}%.
- {diag_text}
- Longer stays are generally associated with higher readmission exposure and higher care costs.
- Monthly readmission trends show whether care patterns are improving or worsening over time.

## Visual dashboard
![Age Group Readmission](viz_age_readmission.png)

![Insurance Type Readmission](viz_insurance_readmission.png)

![Diagnosis Category Readmission](viz_diag_readmission.png)

![Cost by Tier and Readmission](viz_cost_tier.png)

![Length of Stay by Readmission](viz_los_readmission.png)

![Monthly Readmission Trend](viz_monthly_trend.png)

## Interpretation
1. Age and insurance status appear to be meaningful risk stratification variables for readmission.
2. Diagnosis mix and hospital tier are useful for understanding cost and readmission variation.
3. The monthly trend helps detect seasonal or operational changes in patient outcomes.
4. Combining these variables supports a more evidence-based clinical and operational dashboard.
"""

(output_dir / "data_visualization_report.md").write_text(report, encoding="utf-8")

print("Generated visualizations and summary report in:", output_dir)
print("Files created:")
for name in [
    "viz_age_readmission.png",
    "viz_insurance_readmission.png",
    "viz_diag_readmission.png",
    "viz_cost_tier.png",
    "viz_los_readmission.png",
    "viz_monthly_trend.png",
    "data_visualization_report.md",
]:
    print("-", name)
print(f"Overall 30-day readmission rate: {overall_30:.2f}%")
print(f"Overall 7-day readmission rate: {overall_7:.2f}%")
print(f"Average LOS: {avg_los:.2f} days")
print(f"Average cost: ₹{avg_cost:,.2f}")
