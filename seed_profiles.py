"""Seed 5 dummy borrower profiles into the profile service."""
import requests
import json

BASE = "http://127.0.0.1:8001/api/v1/profiles"

profiles = [
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
            {"season": "KHARIF", "income_multiplier": 1.3, "expense_multiplier": 1.4, "description": "Monsoon cultivation"},
            {"season": "RABI", "income_multiplier": 1.1, "expense_multiplier": 1.0, "description": "Winter cultivation"},
            {"season": "ZAID", "income_multiplier": 0.6, "expense_multiplier": 0.6, "description": "Summer off-season"},
        ],
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
            {"season": "ZAID", "income_multiplier": 0.4, "expense_multiplier": 0.5, "description": "Summer off-season"},
        ],
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
    },
]

print("Creating profiles...")
created_ids = []
for p in profiles:
    r = requests.post(BASE, json=p)
    name = p["personal_info"]["name"]
    if r.status_code == 201:
        pid = r.json()["profile_id"]
        created_ids.append(pid)
        print(f"  [OK] {name} -> {pid}")
    else:
        print(f"  [FAIL] {name} -> {r.status_code}: {r.text[:200]}")

# Verify list
print("\nVerifying list endpoint...")
r2 = requests.get(BASE + "?limit=50")
data = r2.json()
items = data["items"]
print(f"  {len(items)} profiles returned")
for item in items:
    print(f"  - {item['name']} ({item['location']}, {item['occupation']})")
