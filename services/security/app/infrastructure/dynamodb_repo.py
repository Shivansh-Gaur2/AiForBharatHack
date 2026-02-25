"""DynamoDB repository for the Security & Privacy service.

Single-table design with access patterns:
- Consent:   PK=CONSENT#{id}                   SK=METADATA
              PK=PROFILE_CONSENT#{profile_id}   SK=PURPOSE#{purpose}
- Audit:     PK=AUDIT#{profile_id}              SK=TS#{iso}#{entry_id}
- Lineage:   PK=LINEAGE#{profile_id}            SK=TS#{iso}#{record_id}
- Retention: PK=RETENTION_POLICY                SK=CATEGORY#{category}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from ..domain.models import (
    AuditAction,
    AuditEntry,
    Consent,
    ConsentPurpose,
    ConsentStatus,
    DataCategory,
    DataLineageRecord,
    RetentionAction,
    RetentionPolicy,
)

logger = logging.getLogger(__name__)


def _dt_to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _iso_to_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


class DynamoDBSecurityRepository:
    """Implements all four repository interfaces against DynamoDB."""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    # ==================================================================
    # Consent Repository
    # ==================================================================

    async def save_consent(self, consent: Consent) -> None:
        item = self._consent_to_item(consent)
        self._table.put_item(Item=item)
        # Also store by profile+purpose for active-consent lookups
        self._table.put_item(Item={
            "PK": f"PROFILE_CONSENT#{consent.profile_id}",
            "SK": f"PURPOSE#{consent.purpose.value}",
            "consent_id": consent.consent_id,
            **self._consent_fields(consent),
        })

    async def find_consent_by_id(self, consent_id: str) -> Consent | None:
        resp = self._table.get_item(Key={
            "PK": f"CONSENT#{consent_id}",
            "SK": "METADATA",
        })
        item = resp.get("Item")
        return self._item_to_consent(item) if item else None

    async def find_consents_by_profile(self, profile_id: str) -> list[Consent]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": f"PROFILE_CONSENT#{profile_id}",
                ":prefix": "PURPOSE#",
            },
        )
        return [self._item_to_consent(i) for i in resp.get("Items", [])]

    async def find_active_consent(
        self, profile_id: str, purpose: ConsentPurpose,
    ) -> Consent | None:
        resp = self._table.get_item(Key={
            "PK": f"PROFILE_CONSENT#{profile_id}",
            "SK": f"PURPOSE#{purpose.value}",
        })
        item = resp.get("Item")
        if not item:
            return None
        return self._item_to_consent(item)

    async def update_consent(self, consent: Consent) -> None:
        await self.save_consent(consent)

    def _consent_fields(self, c: Consent) -> dict:
        return {
            "profile_id": c.profile_id,
            "purpose": c.purpose.value,
            "status": c.status.value,
            "granted_at": _dt_to_iso(c.granted_at),
            "expires_at": _dt_to_iso(c.expires_at),
            "revoked_at": _dt_to_iso(c.revoked_at) if c.revoked_at else "",
            "granted_by": c.granted_by,
            "revocation_reason": c.revocation_reason,
            "version": c.version,
        }

    def _consent_to_item(self, c: Consent) -> dict:
        return {
            "PK": f"CONSENT#{c.consent_id}",
            "SK": "METADATA",
            "consent_id": c.consent_id,
            **self._consent_fields(c),
        }

    def _item_to_consent(self, item: dict) -> Consent:
        revoked_at_str = item.get("revoked_at", "")
        return Consent(
            consent_id=item["consent_id"],
            profile_id=item["profile_id"],
            purpose=ConsentPurpose(item["purpose"]),
            status=ConsentStatus(item["status"]),
            granted_at=_iso_to_dt(item["granted_at"]),
            expires_at=_iso_to_dt(item["expires_at"]),
            revoked_at=_iso_to_dt(revoked_at_str) if revoked_at_str else None,
            granted_by=item.get("granted_by", ""),
            revocation_reason=item.get("revocation_reason", ""),
            version=int(item.get("version", 1)),
        )

    # ==================================================================
    # Audit Repository
    # ==================================================================

    async def save_entry(self, entry: AuditEntry) -> None:
        self._table.put_item(Item={
            "PK": f"AUDIT#{entry.profile_id}",
            "SK": f"TS#{_dt_to_iso(entry.timestamp)}#{entry.entry_id}",
            "entry_id": entry.entry_id,
            "timestamp": _dt_to_iso(entry.timestamp),
            "actor_id": entry.actor_id,
            "action": entry.action.value,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "profile_id": entry.profile_id,
            "details": json.dumps(entry.details),
            "ip_address": entry.ip_address,
            "user_agent": entry.user_agent,
            "success": entry.success,
        })

    async def find_entries_by_profile(
        self, profile_id: str, limit: int = 50,
    ) -> list[AuditEntry]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": f"AUDIT#{profile_id}",
                ":prefix": "TS#",
            },
            ScanIndexForward=False,
            Limit=limit,
        )
        return [self._item_to_audit(i) for i in resp.get("Items", [])]

    async def find_entries_by_actor(
        self, actor_id: str, limit: int = 50,
    ) -> list[AuditEntry]:
        # Scan with filter — acceptable for low-frequency admin queries
        resp = self._table.scan(
            FilterExpression="actor_id = :actor AND begins_with(PK, :prefix)",
            ExpressionAttributeValues={
                ":actor": actor_id,
                ":prefix": "AUDIT#",
            },
            Limit=limit,
        )
        return [self._item_to_audit(i) for i in resp.get("Items", [])]

    async def find_entries_by_action(
        self, action: str, limit: int = 50,
    ) -> list[AuditEntry]:
        resp = self._table.scan(
            FilterExpression="#act = :action AND begins_with(PK, :prefix)",
            ExpressionAttributeNames={"#act": "action"},
            ExpressionAttributeValues={
                ":action": action,
                ":prefix": "AUDIT#",
            },
            Limit=limit,
        )
        return [self._item_to_audit(i) for i in resp.get("Items", [])]

    def _item_to_audit(self, item: dict) -> AuditEntry:
        return AuditEntry(
            entry_id=item["entry_id"],
            timestamp=_iso_to_dt(item["timestamp"]),
            actor_id=item["actor_id"],
            action=AuditAction(item["action"]),
            resource_type=item["resource_type"],
            resource_id=item["resource_id"],
            profile_id=item["profile_id"],
            details=json.loads(item.get("details", "{}")),
            ip_address=item.get("ip_address", ""),
            user_agent=item.get("user_agent", ""),
            success=item.get("success", True),
        )

    # ==================================================================
    # Data Lineage Repository
    # ==================================================================

    async def save_record(self, record: DataLineageRecord) -> None:
        self._table.put_item(Item={
            "PK": f"LINEAGE#{record.profile_id}",
            "SK": f"TS#{_dt_to_iso(record.timestamp)}#{record.record_id}",
            "record_id": record.record_id,
            "timestamp": _dt_to_iso(record.timestamp),
            "profile_id": record.profile_id,
            "data_category": record.data_category.value,
            "source_service": record.source_service,
            "target_service": record.target_service,
            "action": record.action,
            "fields_accessed": json.dumps(record.fields_accessed),
            "purpose": record.purpose,
            "consent_id": record.consent_id,
            "actor_id": record.actor_id,
        })

    async def find_records_by_profile(
        self, profile_id: str, limit: int = 100,
    ) -> list[DataLineageRecord]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": f"LINEAGE#{profile_id}",
                ":prefix": "TS#",
            },
            ScanIndexForward=False,
            Limit=limit,
        )
        return [self._item_to_lineage(i) for i in resp.get("Items", [])]

    async def find_records_by_category(
        self, profile_id: str, category: DataCategory,
    ) -> list[DataLineageRecord]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            FilterExpression="data_category = :cat",
            ExpressionAttributeValues={
                ":pk": f"LINEAGE#{profile_id}",
                ":prefix": "TS#",
                ":cat": category.value,
            },
        )
        return [self._item_to_lineage(i) for i in resp.get("Items", [])]

    def _item_to_lineage(self, item: dict) -> DataLineageRecord:
        return DataLineageRecord(
            record_id=item["record_id"],
            timestamp=_iso_to_dt(item["timestamp"]),
            profile_id=item["profile_id"],
            data_category=DataCategory(item["data_category"]),
            source_service=item["source_service"],
            target_service=item["target_service"],
            action=item["action"],
            fields_accessed=json.loads(item.get("fields_accessed", "[]")),
            purpose=item.get("purpose", ""),
            consent_id=item.get("consent_id", ""),
            actor_id=item.get("actor_id", ""),
        )

    # ==================================================================
    # Retention Policy Repository
    # ==================================================================

    async def save_policy(self, policy: RetentionPolicy) -> None:
        self._table.put_item(Item={
            "PK": "RETENTION_POLICY",
            "SK": f"CATEGORY#{policy.data_category.value}",
            "policy_id": policy.policy_id,
            "data_category": policy.data_category.value,
            "retention_days": policy.retention_days,
            "action": policy.action.value,
            "description": policy.description,
            "is_active": policy.is_active,
            "created_at": _dt_to_iso(policy.created_at),
        })

    async def find_all_policies(self) -> list[RetentionPolicy]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": "RETENTION_POLICY",
                ":prefix": "CATEGORY#",
            },
        )
        return [self._item_to_policy(i) for i in resp.get("Items", [])]

    async def find_policy_by_category(
        self, category: DataCategory,
    ) -> RetentionPolicy | None:
        resp = self._table.get_item(Key={
            "PK": "RETENTION_POLICY",
            "SK": f"CATEGORY#{category.value}",
        })
        item = resp.get("Item")
        return self._item_to_policy(item) if item else None

    def _item_to_policy(self, item: dict) -> RetentionPolicy:
        return RetentionPolicy(
            policy_id=item["policy_id"],
            data_category=DataCategory(item["data_category"]),
            retention_days=int(item["retention_days"]),
            action=RetentionAction(item["action"]),
            description=item.get("description", ""),
            is_active=item.get("is_active", True),
            created_at=_iso_to_dt(item["created_at"]),
        )
