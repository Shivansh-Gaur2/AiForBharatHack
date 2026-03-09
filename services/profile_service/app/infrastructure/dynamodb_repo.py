"""DynamoDB repository — implements ProfileRepository port.

Uses single-table design with the following access patterns:
- PK: PROFILE#{profile_id}   SK: METADATA       → Profile data
- PK: PHONE#{phone}          SK: PROFILE_REF     → Phone → profile_id lookup
- PK: DISTRICT#{state}#{district}  SK: PROFILE#{id} → District index

For DynamoDB Local (dev), set endpoint_url in config.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from services.profile_service.app.domain.models import (
    BorrowerProfile,
    BusinessDetails,
    CropInfo,
    ExpenseRecord,
    IncomeRecord,
    LandDetails,
    LivelihoodInfo,
    LivestockInfo,
    MigrationInfo,
    PersonalInfo,
    SeasonalFactor,
    VolatilityMetrics,
)
from services.shared.models import OccupationType, Season

logger = logging.getLogger(__name__)


class DynamoDBProfileRepository:
    """Concrete adapter implementing the ProfileRepository port.

    If a ``FieldEncryptor`` is provided, sensitive PII fields (phone, name,
    bank details) are encrypted at rest using field-level encryption (Req 9.1).
    """

    def __init__(
        self,
        dynamodb_resource: Any,
        table_name: str,
        field_encryptor: Any | None = None,
    ) -> None:
        self._table = dynamodb_resource.Table(table_name)
        self._table_name = table_name
        self._enc = field_encryptor  # FieldEncryptor | None

    # ------------------------------------------------------------------
    # ProfileRepository interface
    # ------------------------------------------------------------------

    def save(self, profile: BorrowerProfile) -> None:
        """Persist a profile using DynamoDB put_item (upsert)."""
        item = self._to_dynamodb_item(profile)
        self._table.put_item(Item=item)

        # Secondary index: phone lookup
        if profile.personal_info.phone:
            self._table.put_item(Item={
                "PK": f"PHONE#{profile.personal_info.phone}",
                "SK": "PROFILE_REF",
                "profile_id": profile.profile_id,
            })

        # Secondary index: district lookup
        self._table.put_item(Item={
            "PK": f"DISTRICT#{profile.personal_info.state}#{profile.personal_info.district}",
            "SK": f"PROFILE#{profile.profile_id}",
            "profile_id": profile.profile_id,
            "name": profile.personal_info.name,
        })

        logger.debug("Saved profile %s to DynamoDB", profile.profile_id)

    def find_by_id(self, profile_id: str) -> BorrowerProfile | None:
        """Retrieve a profile by its ID."""
        response = self._table.get_item(
            Key={"PK": f"PROFILE#{profile_id}", "SK": "METADATA"}
        )
        item = response.get("Item")
        if not item:
            return None
        return self._from_dynamodb_item(item)

    def find_by_phone(self, phone: str) -> BorrowerProfile | None:
        """Retrieve a profile by phone number (via secondary index)."""
        response = self._table.get_item(
            Key={"PK": f"PHONE#{phone}", "SK": "PROFILE_REF"}
        )
        ref = response.get("Item")
        if not ref:
            return None
        return self.find_by_id(ref["profile_id"])

    def find_by_district(self, district: str, state: str) -> list[BorrowerProfile]:
        """Retrieve profiles by district using the district index."""
        from boto3.dynamodb.conditions import Key

        response = self._table.query(
            KeyConditionExpression=Key("PK").eq(f"DISTRICT#{state}#{district}")
            & Key("SK").begins_with("PROFILE#")
        )
        profiles = []
        for item in response.get("Items", []):
            profile = self.find_by_id(item["profile_id"])
            if profile:
                profiles.append(profile)
        return profiles

    def delete(self, profile_id: str) -> None:
        """Delete a profile and its secondary index entries."""
        profile = self.find_by_id(profile_id)
        if not profile:
            return

        # Delete main record
        self._table.delete_item(
            Key={"PK": f"PROFILE#{profile_id}", "SK": "METADATA"}
        )

        # Delete phone index
        if profile.personal_info.phone:
            self._table.delete_item(
                Key={"PK": f"PHONE#{profile.personal_info.phone}", "SK": "PROFILE_REF"}
            )

        # Delete district index
        self._table.delete_item(
            Key={
                "PK": f"DISTRICT#{profile.personal_info.state}#{profile.personal_info.district}",
                "SK": f"PROFILE#{profile_id}",
            }
        )

    def list_all(
        self, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[BorrowerProfile], str | None]:
        """List profiles with cursor-based pagination using a scan."""
        scan_kwargs: dict[str, Any] = {
            "FilterExpression": "begins_with(PK, :pk_prefix) AND SK = :sk",
            "ExpressionAttributeValues": {
                ":pk_prefix": "PROFILE#",
                ":sk": "METADATA",
            },
            "Limit": limit,
        }
        if cursor:
            scan_kwargs["ExclusiveStartKey"] = json.loads(cursor)

        response = self._table.scan(**scan_kwargs)
        profiles = [self._from_dynamodb_item(item) for item in response.get("Items", [])]
        next_cursor = None
        if "LastEvaluatedKey" in response:
            next_cursor = json.dumps(response["LastEvaluatedKey"])

        return profiles, next_cursor

    # ------------------------------------------------------------------
    # Serialization — Domain ↔ DynamoDB
    # ------------------------------------------------------------------

    def _to_dynamodb_item(self, profile: BorrowerProfile) -> dict[str, Any]:
        """Serialize domain entity → DynamoDB item.

        Encrypts sensitive PII fields when a FieldEncryptor is configured.
        """
        personal = {
            "name": profile.personal_info.name,
            "age": profile.personal_info.age,
            "gender": profile.personal_info.gender,
            "district": profile.personal_info.district,
            "state": profile.personal_info.state,
            "dependents": profile.personal_info.dependents,
            "phone": profile.personal_info.phone,
            "location": profile.personal_info.location,
        }

        # Encrypt PII fields if encryptor is available
        if self._enc is not None:
            personal = self._enc.encrypt_dict(personal, ["name", "phone"])

        return {
            "PK": f"PROFILE#{profile.profile_id}",
            "SK": "METADATA",
            "profile_id": profile.profile_id,
            "personal_info": personal,
            "livelihood_info": {
                "primary_occupation": profile.livelihood_info.primary_occupation.value,
                "secondary_occupations": [o.value for o in profile.livelihood_info.secondary_occupations],
                "land_holding": {
                    "total_acres": str(profile.livelihood_info.land_holding.total_acres),
                    "irrigated_acres": str(profile.livelihood_info.land_holding.irrigated_acres),
                    "rain_fed_acres": str(profile.livelihood_info.land_holding.rain_fed_acres),
                    "ownership_type": profile.livelihood_info.land_holding.ownership_type,
                } if profile.livelihood_info.land_holding else None,
                "crop_patterns": [
                    {
                        "crop_name": c.crop_name,
                        "season": c.season.value,
                        "area_acres": str(c.area_acres),
                        "expected_yield_quintals": str(c.expected_yield_quintals),
                        "expected_price_per_quintal": str(c.expected_price_per_quintal),
                    } for c in profile.livelihood_info.crop_patterns
                ],
                "livestock": [
                    {
                        "animal_type": l.animal_type,
                        "count": l.count,
                        "monthly_income": str(l.monthly_income),
                        "monthly_expense": str(l.monthly_expense),
                    } for l in profile.livelihood_info.livestock
                ],
                "migration_patterns": [
                    {
                        "destination": m.destination,
                        "months": m.months,
                        "monthly_income": str(m.monthly_income),
                    } for m in profile.livelihood_info.migration_patterns
                ],
                "business_details": {
                    "business_type": profile.livelihood_info.business_details.business_type,
                    "workspace_owned": profile.livelihood_info.business_details.workspace_owned,
                    "workspace_description": profile.livelihood_info.business_details.workspace_description,
                    "monthly_revenue": str(profile.livelihood_info.business_details.monthly_revenue),
                    "monthly_expenses": str(profile.livelihood_info.business_details.monthly_expenses),
                    "investment_amount": str(profile.livelihood_info.business_details.investment_amount),
                    "years_in_business": profile.livelihood_info.business_details.years_in_business,
                } if profile.livelihood_info.business_details else None,
            },
            "income_records": [
                {
                    "month": r.month, "year": r.year,
                    "amount": str(r.amount), "source": r.source,
                    "is_verified": r.is_verified,
                } for r in profile.income_records
            ],
            "expense_records": [
                {
                    "month": r.month, "year": r.year,
                    "amount": str(r.amount), "category": r.category,
                } for r in profile.expense_records
            ],
            "seasonal_factors": [
                {
                    "season": f.season.value,
                    "income_multiplier": str(f.income_multiplier),
                    "expense_multiplier": str(f.expense_multiplier),
                    "notes": f.notes,
                } for f in profile.seasonal_factors
            ],
            "volatility_metrics": {
                "coefficient_of_variation": str(profile.volatility_metrics.coefficient_of_variation),
                "income_range_ratio": str(profile.volatility_metrics.income_range_ratio),
                "seasonal_variance": str(profile.volatility_metrics.seasonal_variance),
                "months_below_average": profile.volatility_metrics.months_below_average,
                "volatility_category": profile.volatility_metrics.volatility_category,
            } if profile.volatility_metrics else None,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
        }

    def _from_dynamodb_item(self, item: dict[str, Any]) -> BorrowerProfile:
        """Deserialize DynamoDB item → domain entity.

        Decrypts PII fields when a FieldEncryptor is configured.
        """
        pi = item["personal_info"]

        # Decrypt PII fields if encryptor is available
        if self._enc is not None:
            pi = self._enc.decrypt_dict(pi, ["name", "phone"])

        li = item["livelihood_info"]

        land_holding = None
        if li.get("land_holding"):
            lh = li["land_holding"]
            land_holding = LandDetails(
                total_acres=float(lh["total_acres"]),
                irrigated_acres=float(lh["irrigated_acres"]),
                rain_fed_acres=float(lh["rain_fed_acres"]),
                ownership_type=lh["ownership_type"],
            )

        biz = None
        if li.get("business_details"):
            bd = li["business_details"]
            biz = BusinessDetails(
                business_type=bd["business_type"],
                workspace_owned=bd.get("workspace_owned", False),
                workspace_description=bd.get("workspace_description", ""),
                monthly_revenue=float(bd.get("monthly_revenue", 0)),
                monthly_expenses=float(bd.get("monthly_expenses", 0)),
                investment_amount=float(bd.get("investment_amount", 0)),
                years_in_business=int(bd.get("years_in_business", 0)),
            )

        livelihood_info = LivelihoodInfo(
            primary_occupation=OccupationType(li["primary_occupation"]),
            secondary_occupations=[OccupationType(o) for o in li.get("secondary_occupations", [])],
            land_holding=land_holding,
            crop_patterns=[
                CropInfo(
                    crop_name=c["crop_name"],
                    season=Season(c["season"]),
                    area_acres=float(c["area_acres"]),
                    expected_yield_quintals=float(c["expected_yield_quintals"]),
                    expected_price_per_quintal=float(c["expected_price_per_quintal"]),
                ) for c in li.get("crop_patterns", [])
            ],
            livestock=[
                LivestockInfo(
                    animal_type=l["animal_type"],
                    count=int(l["count"]),
                    monthly_income=float(l["monthly_income"]),
                    monthly_expense=float(l["monthly_expense"]),
                ) for l in li.get("livestock", [])
            ],
            migration_patterns=[
                MigrationInfo(
                    destination=m["destination"],
                    months=m["months"],
                    monthly_income=float(m["monthly_income"]),
                ) for m in li.get("migration_patterns", [])
            ],
            business_details=biz,
        )

        volatility_metrics = None
        if item.get("volatility_metrics"):
            vm = item["volatility_metrics"]
            volatility_metrics = VolatilityMetrics(
                coefficient_of_variation=float(vm["coefficient_of_variation"]),
                income_range_ratio=float(vm["income_range_ratio"]),
                seasonal_variance=float(vm["seasonal_variance"]),
                months_below_average=int(vm["months_below_average"]),
                volatility_category=vm["volatility_category"],
            )

        return BorrowerProfile(
            profile_id=item["profile_id"],
            personal_info=PersonalInfo(
                name=pi["name"],
                age=int(pi["age"]),
                gender=pi["gender"],
                district=pi["district"],
                state=pi["state"],
                dependents=int(pi["dependents"]),
                phone=pi.get("phone"),
                location=pi.get("location", ""),
            ),
            livelihood_info=livelihood_info,
            income_records=[
                IncomeRecord(
                    month=int(r["month"]), year=int(r["year"]),
                    amount=float(r["amount"]), source=r["source"],
                    is_verified=r.get("is_verified", False),
                ) for r in item.get("income_records", [])
            ],
            expense_records=[
                ExpenseRecord(
                    month=int(r["month"]), year=int(r["year"]),
                    amount=float(r["amount"]), category=r["category"],
                ) for r in item.get("expense_records", [])
            ],
            seasonal_factors=[
                SeasonalFactor(
                    season=Season(f["season"]),
                    income_multiplier=float(f["income_multiplier"]),
                    expense_multiplier=float(f["expense_multiplier"]),
                    notes=f.get("notes", ""),
                ) for f in item.get("seasonal_factors", [])
            ],
            volatility_metrics=volatility_metrics,
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )
