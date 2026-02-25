"""DynamoDB repository — implements LoanRepository port.

Single-table design with access patterns:
- PK: LOAN#{tracking_id}         SK: METADATA      → Loan data
- PK: BORROWER_LOANS#{profile_id} SK: LOAN#{id}    → Profile → loans index
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from services.loan_tracker.app.domain.models import (
    Loan,
    LoanTerms,
    RepaymentRecord,
)
from services.shared.models import LoanSourceType, LoanStatus

logger = logging.getLogger(__name__)


class DynamoDBLoanRepository:
    """Concrete adapter implementing the LoanRepository port."""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)
        self._table_name = table_name

    # ------------------------------------------------------------------
    # LoanRepository interface
    # ------------------------------------------------------------------

    async def save(self, loan: Loan) -> None:
        """Persist a loan (upsert)."""
        item = self._to_item(loan)
        self._table.put_item(Item=item)

        # Secondary index: borrower → loan
        self._table.put_item(Item={
            "PK": f"BORROWER_LOANS#{loan.profile_id}",
            "SK": f"LOAN#{loan.tracking_id}",
            "tracking_id": loan.tracking_id,
            "lender_name": loan.lender_name,
            "source_type": loan.source_type.value,
            "principal": str(loan.terms.principal),
            "outstanding_balance": str(loan.outstanding_balance),
            "status": loan.status.value,
            "emi_amount": str(loan.terms.emi_amount),
        })

        logger.debug("Saved loan %s to DynamoDB", loan.tracking_id)

    async def find_by_id(self, tracking_id: str) -> Loan | None:
        response = self._table.get_item(
            Key={"PK": f"LOAN#{tracking_id}", "SK": "METADATA"}
        )
        item = response.get("Item")
        if not item:
            return None
        return self._from_item(item)

    async def find_by_profile(
        self,
        profile_id: str,
        active_only: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Loan], str | None]:
        """Get all loans for a profile using the BORROWER_LOANS index."""
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
            "ExpressionAttributeValues": {
                ":pk": f"BORROWER_LOANS#{profile_id}",
                ":sk_prefix": "LOAN#",
            },
            "Limit": limit,
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = json.loads(cursor)

        response = self._table.query(**kwargs)
        index_items = response.get("Items", [])

        # Fetch full loan data for each
        loans: list[Loan] = []
        for idx_item in index_items:
            loan = await self.find_by_id(idx_item["tracking_id"])
            if loan is None:
                continue
            if active_only and loan.status != LoanStatus.ACTIVE:
                continue
            loans.append(loan)

        next_cursor = None
        if "LastEvaluatedKey" in response:
            next_cursor = json.dumps(response["LastEvaluatedKey"])

        return loans, next_cursor

    async def delete(self, tracking_id: str) -> bool:
        loan = await self.find_by_id(tracking_id)
        if loan is None:
            return False

        self._table.delete_item(
            Key={"PK": f"LOAN#{tracking_id}", "SK": "METADATA"}
        )
        self._table.delete_item(
            Key={
                "PK": f"BORROWER_LOANS#{loan.profile_id}",
                "SK": f"LOAN#{tracking_id}",
            }
        )
        logger.debug("Deleted loan %s", tracking_id)
        return True

    async def list_all(
        self,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Loan], str | None]:
        kwargs: dict[str, Any] = {
            "FilterExpression": "SK = :meta",
            "ExpressionAttributeValues": {":meta": "METADATA"},
            "Limit": limit * 3,  # overscan because filter is post-scan
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = json.loads(cursor)

        response = self._table.scan(**kwargs)
        items = response.get("Items", [])

        loans = [self._from_item(it) for it in items if it.get("PK", "").startswith("LOAN#")]
        loans = loans[:limit]

        next_cursor = None
        if "LastEvaluatedKey" in response:
            next_cursor = json.dumps(response["LastEvaluatedKey"])

        return loans, next_cursor

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _to_item(self, loan: Loan) -> dict[str, Any]:
        repayments = [
            {
                "date": r.date.isoformat(),
                "amount": str(r.amount),
                "is_late": r.is_late,
                "days_overdue": r.days_overdue,
            }
            for r in loan.repayments
        ]

        return {
            "PK": f"LOAN#{loan.tracking_id}",
            "SK": "METADATA",
            "tracking_id": loan.tracking_id,
            "profile_id": loan.profile_id,
            "lender_name": loan.lender_name,
            "source_type": loan.source_type.value,
            "status": loan.status.value,
            "principal": str(loan.terms.principal),
            "interest_rate_annual": str(loan.terms.interest_rate_annual),
            "tenure_months": loan.terms.tenure_months,
            "emi_amount": str(loan.terms.emi_amount),
            "collateral_description": loan.terms.collateral_description or "",
            "disbursement_date": loan.disbursement_date.isoformat(),
            "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else "",
            "outstanding_balance": str(loan.outstanding_balance),
            "total_repaid": str(loan.total_repaid),
            "repayments": json.dumps(repayments),
            "purpose": loan.purpose,
            "notes": loan.notes,
            "created_at": loan.created_at.isoformat(),
            "updated_at": loan.updated_at.isoformat(),
        }

    def _from_item(self, item: dict[str, Any]) -> Loan:
        repayments_raw = json.loads(item.get("repayments", "[]"))
        repayments = [
            RepaymentRecord(
                date=datetime.fromisoformat(r["date"]),
                amount=float(r["amount"]),
                is_late=r.get("is_late", False),
                days_overdue=r.get("days_overdue", 0),
            )
            for r in repayments_raw
        ]

        maturity_str = item.get("maturity_date", "")
        maturity_date = datetime.fromisoformat(maturity_str) if maturity_str else None

        return Loan(
            tracking_id=item["tracking_id"],
            profile_id=item["profile_id"],
            lender_name=item["lender_name"],
            source_type=LoanSourceType(item["source_type"]),
            terms=LoanTerms(
                principal=float(item["principal"]),
                interest_rate_annual=float(item["interest_rate_annual"]),
                tenure_months=int(item["tenure_months"]),
                emi_amount=float(item["emi_amount"]),
                collateral_description=item.get("collateral_description") or None,
            ),
            status=LoanStatus(item["status"]),
            disbursement_date=datetime.fromisoformat(item["disbursement_date"]),
            maturity_date=maturity_date,
            outstanding_balance=float(item["outstanding_balance"]),
            total_repaid=float(item["total_repaid"]),
            repayments=repayments,
            purpose=item.get("purpose", ""),
            notes=item.get("notes", ""),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )
