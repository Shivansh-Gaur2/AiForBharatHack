"""
Seed realistic demo data into the deployed AWS production services.

Seeds: Profiles → Loans → Cash Flow → Risk Scores → Early Warnings → Guidance
Run:   python seed_production.py
"""

import random
import requests
import json
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════════
# Production API URLs
# ═══════════════════════════════════════════════════════════════════════════════
import sys

# Toggle: pass --prod to seed AWS, otherwise seed local
_LOCAL = "--prod" not in sys.argv

if _LOCAL:
    URLS = {
        "profile":       "http://127.0.0.1:8001",
        "loan":          "http://127.0.0.1:8002",
        "risk":          "http://127.0.0.1:8003",
        "cashflow":      "http://127.0.0.1:8004",
        "early_warning": "http://127.0.0.1:8005",
        "guidance":      "http://127.0.0.1:8006",
    }
else:
    URLS = {
        "profile":       "https://femujje0hj.execute-api.us-east-1.amazonaws.com",
        "loan":          "https://068aqecn2j.execute-api.us-east-1.amazonaws.com",
        "risk":          "https://54t4r7xt4k.execute-api.us-east-1.amazonaws.com",
        "cashflow":      "https://0d90oqcz5c.execute-api.us-east-1.amazonaws.com",
        "early_warning": "https://l9u8ls8k0f.execute-api.us-east-1.amazonaws.com",
        "guidance":      "https://77qr8f1p10.execute-api.us-east-1.amazonaws.com",
    }

# ═══════════════════════════════════════════════════════════════════════════════
# 1. PROFILES — 5 diverse rural borrowers
# ═══════════════════════════════════════════════════════════════════════════════
PROFILES = [
    {
        "personal_info": {
            "name": "Ramesh Kumar",
            "age": 45,
            "gender": "male",
            "location": "Karnal",
            "district": "Karnal",
            "state": "Haryana",
            "phone": "9876543210",
            "dependents": 4,
        },
        "livelihood_info": {
            "primary_occupation": "FARMER",
            "secondary_occupations": [],
            "land_details": {"owned_acres": 8.0, "leased_acres": 2.0, "irrigated_percentage": 80},
            "crops": [
                {"crop_name": "Wheat", "season": "RABI", "area_acres": 5.0, "expected_yield_quintals": 25, "expected_price_per_quintal": 2200},
                {"crop_name": "Rice", "season": "KHARIF", "area_acres": 5.0, "expected_yield_quintals": 30, "expected_price_per_quintal": 2000},
            ],
            "livestock": [{"animal_type": "Buffalo", "count": 3, "monthly_income": 4000, "monthly_expense": 2000}],
            "migration_patterns": [],
        },
        "seasonal_factors": [
            {"season": "KHARIF", "income_multiplier": 1.3, "expense_multiplier": 1.4, "description": "Monsoon rice cultivation"},
            {"season": "RABI", "income_multiplier": 1.1, "expense_multiplier": 1.0, "description": "Winter wheat harvest"},
            {"season": "ZAID", "income_multiplier": 0.6, "expense_multiplier": 0.6, "description": "Summer off-season"},
        ],
        "_meta": {"template": "FARMER_LARGE", "risk": "low"},
    },
    {
        "personal_info": {
            "name": "Sunita Devi",
            "age": 38,
            "gender": "female",
            "location": "Amritsar",
            "district": "Amritsar",
            "state": "Punjab",
            "phone": "9123456780",
            "dependents": 3,
        },
        "livelihood_info": {
            "primary_occupation": "FARMER",
            "secondary_occupations": ["LIVESTOCK_REARER"],
            "land_details": {"owned_acres": 4.0, "leased_acres": 1.0, "irrigated_percentage": 60},
            "crops": [
                {"crop_name": "Cotton", "season": "KHARIF", "area_acres": 3.0, "expected_yield_quintals": 10, "expected_price_per_quintal": 6500},
                {"crop_name": "Mustard", "season": "RABI", "area_acres": 2.0, "expected_yield_quintals": 8, "expected_price_per_quintal": 5400},
            ],
            "livestock": [{"animal_type": "Cow", "count": 5, "monthly_income": 8000, "monthly_expense": 3500}],
            "migration_patterns": [],
        },
        "seasonal_factors": [
            {"season": "KHARIF", "income_multiplier": 1.4, "expense_multiplier": 1.3, "description": "Monsoon cultivation"},
            {"season": "RABI", "income_multiplier": 1.0, "expense_multiplier": 0.9, "description": "Winter cultivation"},
            {"season": "ZAID", "income_multiplier": 0.5, "expense_multiplier": 0.5, "description": "Summer off-season"},
        ],
        "_meta": {"template": "FARMER_MEDIUM", "risk": "medium"},
    },
    {
        "personal_info": {
            "name": "Arjun Singh",
            "age": 52,
            "gender": "male",
            "location": "Jaipur",
            "district": "Jaipur",
            "state": "Rajasthan",
            "phone": "9988776655",
            "dependents": 5,
        },
        "livelihood_info": {
            "primary_occupation": "FARMER",
            "secondary_occupations": ["ARTISAN"],
            "land_details": {"owned_acres": 12.0, "leased_acres": 3.0, "irrigated_percentage": 40},
            "crops": [
                {"crop_name": "Bajra", "season": "KHARIF", "area_acres": 8.0, "expected_yield_quintals": 15, "expected_price_per_quintal": 2350},
                {"crop_name": "Gram", "season": "RABI", "area_acres": 7.0, "expected_yield_quintals": 12, "expected_price_per_quintal": 5200},
            ],
            "livestock": [{"animal_type": "Goat", "count": 10, "monthly_income": 3000, "monthly_expense": 1500}],
            "migration_patterns": [],
        },
        "seasonal_factors": [
            {"season": "KHARIF", "income_multiplier": 1.2, "expense_multiplier": 1.3, "description": "Monsoon cultivation"},
            {"season": "RABI", "income_multiplier": 1.1, "expense_multiplier": 1.0, "description": "Winter cultivation"},
            {"season": "ZAID", "income_multiplier": 0.4, "expense_multiplier": 0.5, "description": "Summer off-season — limited irrigation"},
        ],
        "_meta": {"template": "FARMER_LARGE", "risk": "high"},
    },
    {
        "personal_info": {
            "name": "Priya Sharma",
            "age": 29,
            "gender": "female",
            "location": "Lucknow",
            "district": "Lucknow",
            "state": "Uttar Pradesh",
            "phone": "9112233445",
            "dependents": 1,
        },
        "livelihood_info": {
            "primary_occupation": "FARMER",
            "secondary_occupations": [],
            "land_details": {"owned_acres": 3.0, "leased_acres": 0.0, "irrigated_percentage": 90},
            "crops": [
                {"crop_name": "Sugarcane", "season": "KHARIF", "area_acres": 2.0, "expected_yield_quintals": 60, "expected_price_per_quintal": 350},
                {"crop_name": "Potato", "season": "RABI", "area_acres": 1.0, "expected_yield_quintals": 20, "expected_price_per_quintal": 1200},
            ],
            "livestock": [],
            "migration_patterns": [],
        },
        "seasonal_factors": [
            {"season": "KHARIF", "income_multiplier": 1.5, "expense_multiplier": 1.4, "description": "Monsoon cultivation"},
            {"season": "RABI", "income_multiplier": 1.2, "expense_multiplier": 1.1, "description": "Winter cultivation"},
            {"season": "ZAID", "income_multiplier": 0.7, "expense_multiplier": 0.6, "description": "Summer off-season"},
        ],
        "_meta": {"template": "FARMER_SMALL", "risk": "low"},
    },
    {
        "personal_info": {
            "name": "Vikram Patel",
            "age": 41,
            "gender": "male",
            "location": "Anand",
            "district": "Anand",
            "state": "Gujarat",
            "phone": "9334455667",
            "dependents": 3,
        },
        "livelihood_info": {
            "primary_occupation": "LIVESTOCK_REARER",
            "secondary_occupations": ["FARMER"],
            "land_details": {"owned_acres": 2.0, "leased_acres": 1.0, "irrigated_percentage": 100},
            "crops": [
                {"crop_name": "Groundnut", "season": "KHARIF", "area_acres": 2.0, "expected_yield_quintals": 10, "expected_price_per_quintal": 5800},
            ],
            "livestock": [
                {"animal_type": "Buffalo", "count": 8, "monthly_income": 15000, "monthly_expense": 6000},
                {"animal_type": "Cow", "count": 4, "monthly_income": 8000, "monthly_expense": 3000},
            ],
            "migration_patterns": [],
        },
        "seasonal_factors": [
            {"season": "KHARIF", "income_multiplier": 1.1, "expense_multiplier": 1.2, "description": "Monsoon season"},
            {"season": "RABI", "income_multiplier": 1.0, "expense_multiplier": 1.0, "description": "Winter season"},
            {"season": "ZAID", "income_multiplier": 0.8, "expense_multiplier": 0.8, "description": "Summer season"},
        ],
        "_meta": {"template": "LIVESTOCK_PRIMARY", "risk": "medium"},
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# 2. LOANS — realistic formal + informal loans per borrower
# ═══════════════════════════════════════════════════════════════════════════════
LOAN_TEMPLATES = {
    "Ramesh Kumar": [
        {
            "lender_name": "State Bank of India — Karnal Branch",
            "source_type": "FORMAL",
            "terms": {"principal": 300000, "interest_rate_annual": 7.0, "tenure_months": 36, "emi_amount": 9265, "collateral_description": "8 acres agricultural land"},
            "disbursement_date": "2025-04-01T00:00:00",
            "maturity_date": "2028-04-01T00:00:00",
            "purpose": "Kharif crop inputs — seeds, fertilizers, and tractor rental for rice cultivation",
            "notes": "Kisan Credit Card loan, good repayment history",
        },
        {
            "lender_name": "Punjab National Bank",
            "source_type": "FORMAL",
            "terms": {"principal": 150000, "interest_rate_annual": 8.5, "tenure_months": 24, "emi_amount": 6815, "collateral_description": None},
            "disbursement_date": "2025-10-15T00:00:00",
            "maturity_date": "2027-10-15T00:00:00",
            "purpose": "Drip irrigation system installation for wheat fields",
            "notes": "Term loan for irrigation infrastructure",
        },
    ],
    "Sunita Devi": [
        {
            "lender_name": "Amritsar District Cooperative Bank",
            "source_type": "FORMAL",
            "terms": {"principal": 100000, "interest_rate_annual": 9.0, "tenure_months": 18, "emi_amount": 6046, "collateral_description": "Dairy cattle (5 cows)"},
            "disbursement_date": "2025-06-10T00:00:00",
            "maturity_date": "2026-12-10T00:00:00",
            "purpose": "Cotton cultivation — seeds, pesticides and labour advance",
            "notes": "SHG member, first institutional loan",
        },
        {
            "lender_name": "Village money lender — Gurpreet Singh",
            "source_type": "INFORMAL",
            "terms": {"principal": 25000, "interest_rate_annual": 24.0, "tenure_months": 6, "emi_amount": 4500, "collateral_description": None},
            "disbursement_date": "2025-08-20T00:00:00",
            "maturity_date": "2026-02-20T00:00:00",
            "purpose": "Emergency medical expenses — husband's surgery",
            "notes": "High interest informal loan, taken under distress",
        },
    ],
    "Arjun Singh": [
        {
            "lender_name": "Bank of Baroda — Jaipur Rural",
            "source_type": "FORMAL",
            "terms": {"principal": 500000, "interest_rate_annual": 8.0, "tenure_months": 48, "emi_amount": 12189, "collateral_description": "12 acres land + goat herd"},
            "disbursement_date": "2025-03-01T00:00:00",
            "maturity_date": "2029-03-01T00:00:00",
            "purpose": "Solar pump + bore well installation for drought-prone land",
            "notes": "NABARD refinanced, crucial for irrigation in arid region",
        },
        {
            "lender_name": "Jaipur MFI — Sahara Microfinance",
            "source_type": "SEMI_FORMAL",
            "terms": {"principal": 50000, "interest_rate_annual": 18.0, "tenure_months": 12, "emi_amount": 4585, "collateral_description": None},
            "disbursement_date": "2025-09-01T00:00:00",
            "maturity_date": "2026-09-01T00:00:00",
            "purpose": "Working capital for artisan handicraft business (side income)",
            "notes": "Microfinance group loan, weekly repayment converted to monthly EMI",
        },
        {
            "lender_name": "Relative — Bhagirath Singh",
            "source_type": "INFORMAL",
            "terms": {"principal": 30000, "interest_rate_annual": 12.0, "tenure_months": 6, "emi_amount": 5200, "collateral_description": None},
            "disbursement_date": "2025-11-15T00:00:00",
            "maturity_date": "2026-05-15T00:00:00",
            "purpose": "Daughter's school admission fees",
            "notes": "Interest-free family loan, token interest added for tracking",
        },
    ],
    "Priya Sharma": [
        {
            "lender_name": "Gramin Bank of Aryavart",
            "source_type": "FORMAL",
            "terms": {"principal": 75000, "interest_rate_annual": 7.5, "tenure_months": 12, "emi_amount": 6509, "collateral_description": None},
            "disbursement_date": "2025-07-01T00:00:00",
            "maturity_date": "2026-07-01T00:00:00",
            "purpose": "Sugarcane cultivation — seed cane, fertilizers, and harvesting",
            "notes": "PM-KISAN beneficiary, first crop loan",
        },
    ],
    "Vikram Patel": [
        {
            "lender_name": "HDFC Bank — Anand Branch",
            "source_type": "FORMAL",
            "terms": {"principal": 400000, "interest_rate_annual": 9.5, "tenure_months": 36, "emi_amount": 12806, "collateral_description": "8 buffaloes + dairy equipment"},
            "disbursement_date": "2025-02-01T00:00:00",
            "maturity_date": "2028-02-01T00:00:00",
            "purpose": "Dairy expansion — purchase of 4 additional buffaloes + milking machine",
            "notes": "Animal husbandry loan, Amul cooperative member",
        },
        {
            "lender_name": "Anand Cooperative Dairy Society",
            "source_type": "SEMI_FORMAL",
            "terms": {"principal": 60000, "interest_rate_annual": 6.0, "tenure_months": 12, "emi_amount": 5163, "collateral_description": None},
            "disbursement_date": "2025-05-01T00:00:00",
            "maturity_date": "2026-05-01T00:00:00",
            "purpose": "Cattle feed advance for summer months",
            "notes": "Subsidized cooperative loan, deducted from milk payments",
        },
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
# 3. CASHFLOW templates (same as seed_cashflow.py)
# ═══════════════════════════════════════════════════════════════════════════════
CASHFLOW_TEMPLATES = {
    "FARMER_LARGE": {
        "inflows": {
            "CROP_INCOME":        {"base": (10000, 14000), "kharif": 1.4, "rabi": 1.2, "zaid": 0.3},
            "LIVESTOCK_INCOME":   {"base": (3000, 5000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "GOVERNMENT_SUBSIDY": {"base": (500, 1500),    "kharif": 1.5, "rabi": 1.0, "zaid": 0.5},
        },
        "outflows": {
            "SEED_FERTILIZER": {"base": (3000, 5000), "kharif": 1.5, "rabi": 1.2, "zaid": 0.4},
            "LABOUR_EXPENSE":  {"base": (2000, 3500), "kharif": 1.3, "rabi": 1.1, "zaid": 0.5},
            "HOUSEHOLD":       {"base": (4000, 6000), "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "HEALTHCARE":      {"base": (500, 1500),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
    },
    "FARMER_MEDIUM": {
        "inflows": {
            "CROP_INCOME":      {"base": (7000, 10000), "kharif": 1.3, "rabi": 1.1, "zaid": 0.3},
            "LIVESTOCK_INCOME": {"base": (5000, 8000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "OTHER_INCOME":     {"base": (500, 1000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
        "outflows": {
            "SEED_FERTILIZER": {"base": (2000, 3500), "kharif": 1.4, "rabi": 1.2, "zaid": 0.3},
            "LABOUR_EXPENSE":  {"base": (1500, 2500), "kharif": 1.2, "rabi": 1.1, "zaid": 0.4},
            "HOUSEHOLD":       {"base": (3500, 5000), "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "EDUCATION":       {"base": (500, 1000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
    },
    "FARMER_SMALL": {
        "inflows": {
            "CROP_INCOME":        {"base": (5000, 8000), "kharif": 1.5, "rabi": 1.2, "zaid": 0.2},
            "LABOUR_INCOME":      {"base": (2000, 3000), "kharif": 0.8, "rabi": 1.0, "zaid": 1.5},
            "GOVERNMENT_SUBSIDY": {"base": (500, 1000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
        "outflows": {
            "SEED_FERTILIZER": {"base": (1500, 3000), "kharif": 1.5, "rabi": 1.3, "zaid": 0.3},
            "HOUSEHOLD":       {"base": (3000, 4500), "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "HEALTHCARE":      {"base": (300, 800),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
    },
    "LIVESTOCK_PRIMARY": {
        "inflows": {
            "LIVESTOCK_INCOME": {"base": (12000, 18000), "kharif": 1.0, "rabi": 1.1, "zaid": 0.9},
            "CROP_INCOME":      {"base": (3000, 5000),   "kharif": 1.3, "rabi": 1.0, "zaid": 0.2},
            "OTHER_INCOME":     {"base": (1000, 2000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
        "outflows": {
            "SEED_FERTILIZER": {"base": (1000, 2000), "kharif": 1.3, "rabi": 1.0, "zaid": 0.5},
            "LABOUR_EXPENSE":  {"base": (2000, 4000), "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "HOUSEHOLD":       {"base": (4000, 6000), "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "HEALTHCARE":      {"base": (800, 2000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
    },
}

NAME_TO_TEMPLATE = {
    "Ramesh Kumar":  "FARMER_LARGE",
    "Sunita Devi":   "FARMER_MEDIUM",
    "Arjun Singh":   "FARMER_LARGE",
    "Priya Sharma":  "FARMER_SMALL",
    "Vikram Patel":  "LIVESTOCK_PRIMARY",
}

# ═══════════════════════════════════════════════════════════════════════════════
# 4. RISK scoring parameters per profile
# ═══════════════════════════════════════════════════════════════════════════════
RISK_PARAMS = {
    "Ramesh Kumar": {
        "income_volatility_cv": 0.18,
        "annual_income": 280000,
        "months_below_average": 2,
        "debt_to_income_ratio": 0.35,
        "total_outstanding": 380000,
        "active_loan_count": 2,
        "credit_utilisation": 0.45,
        "on_time_repayment_ratio": 0.95,
        "has_defaults": False,
        "seasonal_variance": 0.25,
        "crop_diversification_index": 0.7,
        "weather_risk_score": 20,
        "market_risk_score": 15,
        "dependents": 4,
        "age": 45,
        "has_irrigation": True,
    },
    "Sunita Devi": {
        "income_volatility_cv": 0.35,
        "annual_income": 180000,
        "months_below_average": 4,
        "debt_to_income_ratio": 0.55,
        "total_outstanding": 110000,
        "active_loan_count": 2,
        "credit_utilisation": 0.60,
        "on_time_repayment_ratio": 0.82,
        "has_defaults": False,
        "seasonal_variance": 0.40,
        "crop_diversification_index": 0.5,
        "weather_risk_score": 35,
        "market_risk_score": 40,
        "dependents": 3,
        "age": 38,
        "has_irrigation": False,
    },
    "Arjun Singh": {
        "income_volatility_cv": 0.55,
        "annual_income": 220000,
        "months_below_average": 6,
        "debt_to_income_ratio": 0.75,
        "total_outstanding": 530000,
        "active_loan_count": 3,
        "credit_utilisation": 0.80,
        "on_time_repayment_ratio": 0.70,
        "has_defaults": False,
        "seasonal_variance": 0.55,
        "crop_diversification_index": 0.4,
        "weather_risk_score": 65,
        "market_risk_score": 45,
        "dependents": 5,
        "age": 52,
        "has_irrigation": False,
    },
    "Priya Sharma": {
        "income_volatility_cv": 0.22,
        "annual_income": 130000,
        "months_below_average": 2,
        "debt_to_income_ratio": 0.20,
        "total_outstanding": 60000,
        "active_loan_count": 1,
        "credit_utilisation": 0.25,
        "on_time_repayment_ratio": 0.98,
        "has_defaults": False,
        "seasonal_variance": 0.20,
        "crop_diversification_index": 0.5,
        "weather_risk_score": 15,
        "market_risk_score": 20,
        "dependents": 1,
        "age": 29,
        "has_irrigation": True,
    },
    "Vikram Patel": {
        "income_volatility_cv": 0.28,
        "annual_income": 350000,
        "months_below_average": 3,
        "debt_to_income_ratio": 0.48,
        "total_outstanding": 380000,
        "active_loan_count": 2,
        "credit_utilisation": 0.50,
        "on_time_repayment_ratio": 0.88,
        "has_defaults": False,
        "seasonal_variance": 0.15,
        "crop_diversification_index": 0.3,
        "weather_risk_score": 25,
        "market_risk_score": 30,
        "dependents": 3,
        "age": 41,
        "has_irrigation": True,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# 5. EARLY WARNING parameters per profile
# ═══════════════════════════════════════════════════════════════════════════════
EARLY_WARNING_PARAMS = {
    "Ramesh Kumar": {
        "dti_ratio": 0.35,
        "missed_payments": 0,
        "days_overdue_avg": 0,
        "recent_surplus_trend": [5000, 4800, 5200, 4500, 5100, 4900],
        "risk_category": "LOW",
    },
    "Sunita Devi": {
        "dti_ratio": 0.55,
        "missed_payments": 1,
        "days_overdue_avg": 8,
        "recent_surplus_trend": [2000, 1500, 800, -500, 1200, 600],
        "risk_category": "MEDIUM",
        "alert_type": "REPAYMENT_STRESS",
    },
    "Arjun Singh": {
        "dti_ratio": 0.75,
        "missed_payments": 3,
        "days_overdue_avg": 22,
        "recent_surplus_trend": [1000, -2000, -3500, -1500, -4000, -2800],
        "risk_category": "HIGH",
        "alert_type": "OVER_INDEBTEDNESS",
    },
    "Priya Sharma": {
        "dti_ratio": 0.20,
        "missed_payments": 0,
        "days_overdue_avg": 0,
        "recent_surplus_trend": [3000, 3200, 2800, 3500, 3100, 3400],
        "risk_category": "LOW",
    },
    "Vikram Patel": {
        "dti_ratio": 0.48,
        "missed_payments": 0,
        "days_overdue_avg": 2,
        "recent_surplus_trend": [8000, 7500, 6000, 4500, 7000, 6500],
        "risk_category": "MEDIUM",
        "alert_type": "INCOME_DEVIATION",
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# 6. GUIDANCE loan scenarios per profile
# ═══════════════════════════════════════════════════════════════════════════════
GUIDANCE_TEMPLATES = {
    "Ramesh Kumar": {
        "loan_purpose": "EQUIPMENT_PURCHASE",
        "requested_amount": 450000,
        "tenure_months": 48,
        "interest_rate_annual": 8.5,
        "risk_category": "LOW",
        "risk_score": 720,
        "dti_ratio": 0.35,
        "existing_obligations": 16080,  # sum of EMIs
    },
    "Sunita Devi": {
        "loan_purpose": "LIVESTOCK_PURCHASE",
        "requested_amount": 120000,
        "tenure_months": 24,
        "interest_rate_annual": 10.0,
        "risk_category": "MEDIUM",
        "risk_score": 520,
        "dti_ratio": 0.55,
        "existing_obligations": 10546,
    },
    "Arjun Singh": {
        "loan_purpose": "CROP_CULTIVATION",
        "requested_amount": 80000,
        "tenure_months": 12,
        "interest_rate_annual": 9.0,
        "risk_category": "HIGH",
        "risk_score": 340,
        "dti_ratio": 0.75,
        "existing_obligations": 21974,
    },
    "Priya Sharma": {
        "loan_purpose": "LAND_IMPROVEMENT",
        "requested_amount": 50000,
        "tenure_months": 12,
        "interest_rate_annual": 7.5,
        "risk_category": "LOW",
        "risk_score": 780,
        "dti_ratio": 0.20,
        "existing_obligations": 6509,
    },
    "Vikram Patel": {
        "loan_purpose": "BUSINESS_EXPANSION",
        "requested_amount": 250000,
        "tenure_months": 36,
        "interest_rate_annual": 9.0,
        "risk_category": "MEDIUM",
        "risk_score": 580,
        "dti_ratio": 0.48,
        "existing_obligations": 17969,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _season_for_month(m: int) -> str:
    if m in (6, 7, 8, 9, 10):
        return "kharif"
    elif m in (11, 12, 1, 2, 3):
        return "rabi"
    return "zaid"


def _season_enum(m: int) -> str:
    return {"kharif": "KHARIF", "rabi": "RABI", "zaid": "ZAID"}[_season_for_month(m)]


def generate_cashflow_records(profile_id: str, template_key: str) -> list[dict]:
    tpl = CASHFLOW_TEMPLATES[template_key]
    records = []
    for offset in range(12):
        m = ((2 + offset) % 12) + 1
        y = 2025 if m >= 3 else 2026
        season = _season_for_month(m)

        for cat, cfg in tpl["inflows"].items():
            lo, hi = cfg["base"]
            amount = round(random.uniform(lo, hi) * cfg[season], 2)
            records.append({
                "profile_id": profile_id, "category": cat, "direction": "INFLOW",
                "amount": amount, "month": m, "year": y, "season": _season_enum(m),
                "notes": f"{cat.lower().replace('_', ' ')} — {_season_enum(m).title()} season",
            })

        for cat, cfg in tpl["outflows"].items():
            lo, hi = cfg["base"]
            amount = round(random.uniform(lo, hi) * cfg[season], 2)
            records.append({
                "profile_id": profile_id, "category": cat, "direction": "OUTFLOW",
                "amount": amount, "month": m, "year": y, "season": _season_enum(m),
                "notes": f"{cat.lower().replace('_', ' ')} — {_season_enum(m).title()} season",
            })
    return records


def generate_projections(template_key: str) -> list[dict]:
    """Generate 12-month forward projections for guidance."""
    tpl = CASHFLOW_TEMPLATES[template_key]
    projections = []
    for offset in range(12):
        m = ((2 + offset) % 12) + 1
        y = 2026 if m >= 3 else 2027
        season = _season_for_month(m)

        inflow = sum(
            round(random.uniform(*cfg["base"]) * cfg[season], 2)
            for cfg in tpl["inflows"].values()
        )
        outflow = sum(
            round(random.uniform(*cfg["base"]) * cfg[season], 2)
            for cfg in tpl["outflows"].values()
        )
        projections.append({"month": m, "year": y, "inflow": inflow, "outflow": outflow})
    return projections


def post(url: str, data: dict, label: str) -> dict | None:
    try:
        r = requests.post(url, json=data, timeout=30)
        if r.status_code in (200, 201):
            print(f"    ✓ {label}")
            return r.json()
        else:
            print(f"    ✗ {label} — {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        print(f"    ✗ {label} — {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    random.seed(42)  # reproducible numbers
    profile_map: dict[str, str] = {}  # name → profile_id

    # ── Step 1: Seed Profiles ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 1: Creating farmer profiles")
    print("=" * 60)
    for p in PROFILES:
        payload = {k: v for k, v in p.items() if k != "_meta"}
        name = p["personal_info"]["name"]
        result = post(f"{URLS['profile']}/api/v1/profiles", payload, name)
        if result:
            profile_map[name] = result["profile_id"]

    if not profile_map:
        print("\n  ⚠ No profiles created. Trying to fetch existing ones...")
        r = requests.get(f"{URLS['profile']}/api/v1/profiles?limit=50", timeout=30)
        if r.status_code == 200:
            for item in r.json()["items"]:
                profile_map[item["name"]] = item["profile_id"]
            print(f"  Found {len(profile_map)} existing profiles")

    print(f"\n  Profile IDs:")
    for name, pid in profile_map.items():
        print(f"    {name}: {pid}")

    # ── Step 2: Seed Loans ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 2: Creating loans")
    print("=" * 60)
    for name, loans in LOAN_TEMPLATES.items():
        pid = profile_map.get(name)
        if not pid:
            print(f"  Skipping {name} — no profile ID")
            continue
        print(f"\n  {name}:")
        for loan in loans:
            loan_data = {**loan, "profile_id": pid}
            label = f"{loan['lender_name']} — ₹{loan['terms']['principal']:,.0f}"
            post(f"{URLS['loan']}/api/v1/loans", loan_data, label)

    # ── Step 3: Seed Cash Flow Records ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 3: Seeding 12-month cash flow history")
    print("=" * 60)
    for name, pid in profile_map.items():
        template_key = NAME_TO_TEMPLATE.get(name, "FARMER_MEDIUM")
        records = generate_cashflow_records(pid, template_key)
        print(f"\n  {name} ({len(records)} records, template={template_key}):")
        result = post(
            f"{URLS['cashflow']}/api/v1/cashflow/records/batch",
            {"records": records},
            f"Batch insert {len(records)} records",
        )

    # ── Step 4: Generate Cash Flow Forecasts ────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 4: Generating cash flow forecasts")
    print("=" * 60)
    for name, pid in profile_map.items():
        print(f"\n  {name}:")
        post(
            f"{URLS['cashflow']}/api/v1/cashflow/forecast",
            {"profile_id": pid, "horizon_months": 12},
            "12-month forecast",
        )

    # ── Step 5: Seed Risk Scores ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 5: Computing risk scores")
    print("=" * 60)
    for name, pid in profile_map.items():
        params = RISK_PARAMS.get(name)
        if not params:
            continue
        print(f"\n  {name}:")
        risk_data = {"profile_id": pid, **params}
        post(f"{URLS['risk']}/api/v1/risk/score", risk_data, f"Risk score (DTI={params['debt_to_income_ratio']})")

    # ── Step 6: Seed Early Warning Alerts ───────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 6: Generating early warning alerts")
    print("=" * 60)
    for name, pid in profile_map.items():
        ew_params = EARLY_WARNING_PARAMS.get(name)
        if not ew_params:
            continue
        print(f"\n  {name}:")
        ew_data = {"profile_id": pid, **ew_params}
        post(
            f"{URLS['early_warning']}/api/v1/early-warning/alerts/direct",
            ew_data,
            f"Alert (risk={ew_params['risk_category']}, missed={ew_params['missed_payments']})",
        )

    # ── Step 7: Seed Guidance Recommendations ───────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 7: Generating loan guidance recommendations")
    print("=" * 60)
    for name, pid in profile_map.items():
        guidance = GUIDANCE_TEMPLATES.get(name)
        if not guidance:
            continue
        template_key = NAME_TO_TEMPLATE.get(name, "FARMER_MEDIUM")
        projections = generate_projections(template_key)
        print(f"\n  {name}:")
        guidance_data = {"profile_id": pid, "projections": projections, **guidance}
        post(
            f"{URLS['guidance']}/api/v1/guidance/generate/direct",
            guidance_data,
            f"Guidance — {guidance['loan_purpose'][:50]}…",
        )

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SEEDING COMPLETE!")
    print("=" * 60)
    print(f"  Profiles:       {len(profile_map)}")
    print(f"  Loans:          {sum(len(v) for v in LOAN_TEMPLATES.values())}")
    print(f"  Cash flows:     12 months × {len(profile_map)} profiles")
    print(f"  Risk scores:    {len(RISK_PARAMS)}")
    print(f"  Early warnings: {len(EARLY_WARNING_PARAMS)}")
    print(f"  Guidance:       {len(GUIDANCE_TEMPLATES)}")
    print(f"\n  Frontend: http://rural-credit-frontend-577327405641.s3-website-us-east-1.amazonaws.com")
    print()


if __name__ == "__main__":
    main()
