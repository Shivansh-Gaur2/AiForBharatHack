"""Domain models for the Security & Privacy service.

Covers:
- Consent management (Req 9.3): explicit borrower consent for data sharing
- Data lineage (Req 9.4): audit trail of how borrower data is accessed/used
- Retention policies (Req 9.5): TTL-based auto-deletion of personal data
- Audit log: security event tracking
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

# ===========================================================================
# Identifiers
# ===========================================================================
ConsentId = str
AuditEntryId = str
LineageRecordId = str
RetentionPolicyId = str


def generate_id() -> str:
    return str(uuid.uuid4())


# ===========================================================================
# Enumerations
# ===========================================================================
class ConsentPurpose(StrEnum):
    """What the borrower consents their data to be used for."""
    CREDIT_ASSESSMENT = "CREDIT_ASSESSMENT"
    RISK_SCORING = "RISK_SCORING"
    DATA_SHARING_LENDER = "DATA_SHARING_LENDER"
    DATA_SHARING_CREDIT_BUREAU = "DATA_SHARING_CREDIT_BUREAU"
    MARKETING = "MARKETING"
    RESEARCH_ANONYMIZED = "RESEARCH_ANONYMIZED"
    GOVERNMENT_SCHEME_MATCHING = "GOVERNMENT_SCHEME_MATCHING"
    EARLY_WARNING_ALERTS = "EARLY_WARNING_ALERTS"


class ConsentStatus(StrEnum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class AuditAction(StrEnum):
    """Security-relevant actions tracked in audit log."""
    DATA_ACCESS = "DATA_ACCESS"
    DATA_EXPORT = "DATA_EXPORT"
    DATA_MODIFICATION = "DATA_MODIFICATION"
    DATA_DELETION = "DATA_DELETION"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    ROLE_CHANGE = "ROLE_CHANGE"
    ENCRYPTION_KEY_ROTATION = "ENCRYPTION_KEY_ROTATION"
    RETENTION_PURGE = "RETENTION_PURGE"
    UNAUTHORIZED_ACCESS_ATTEMPT = "UNAUTHORIZED_ACCESS_ATTEMPT"


class DataCategory(StrEnum):
    """Categories of data for lineage tracking and retention."""
    PERSONAL_IDENTITY = "PERSONAL_IDENTITY"   # Aadhaar, PAN, name
    FINANCIAL = "FINANCIAL"                    # Income, loans, accounts
    RISK_ASSESSMENT = "RISK_ASSESSMENT"        # Risk scores, factors
    CASH_FLOW = "CASH_FLOW"                    # Forecasts, actuals
    GUIDANCE = "GUIDANCE"                      # Credit recommendations
    ALERT = "ALERT"                            # Early warnings
    LOCATION = "LOCATION"                      # Village, district, GPS


class RetentionAction(StrEnum):
    DELETE = "DELETE"
    ANONYMIZE = "ANONYMIZE"
    ARCHIVE = "ARCHIVE"


# ===========================================================================
# Consent Aggregate (Req 9.3)
# ===========================================================================
@dataclass
class Consent:
    """Records explicit borrower consent for a specific data use purpose.

    A borrower can grant multiple consents (one per purpose), revoke them
    individually, and consents auto-expire after a configurable period.
    """
    consent_id: str
    profile_id: str
    purpose: ConsentPurpose
    status: ConsentStatus
    granted_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    granted_by: str = ""          # user_id of the person who recorded consent
    revocation_reason: str = ""
    version: int = 1              # consent version — increments on re-grant

    def is_active(self) -> bool:
        if self.status != ConsentStatus.GRANTED:
            return False
        return not datetime.now(UTC) > self.expires_at

    def revoke(self, reason: str = "") -> None:
        if self.status == ConsentStatus.REVOKED:
            raise ValueError("Consent already revoked")
        self.status = ConsentStatus.REVOKED
        self.revoked_at = datetime.now(UTC)
        self.revocation_reason = reason

    def expire(self) -> None:
        if self.status == ConsentStatus.GRANTED:
            self.status = ConsentStatus.EXPIRED

    def renew(self, duration_days: int = 365) -> None:
        """Re-grant consent for another period."""
        self.status = ConsentStatus.GRANTED
        self.granted_at = datetime.now(UTC)
        self.expires_at = self.granted_at + timedelta(days=duration_days)
        self.revoked_at = None
        self.revocation_reason = ""
        self.version += 1


def create_consent(
    profile_id: str,
    purpose: ConsentPurpose,
    granted_by: str = "",
    duration_days: int = 365,
) -> Consent:
    """Factory: create a new consent record."""
    now = datetime.now(UTC)
    return Consent(
        consent_id=generate_id(),
        profile_id=profile_id,
        purpose=purpose,
        status=ConsentStatus.GRANTED,
        granted_at=now,
        expires_at=now + timedelta(days=duration_days),
        granted_by=granted_by,
    )


# ===========================================================================
# Audit Log Entry
# ===========================================================================
@dataclass
class AuditEntry:
    """Immutable record of a security-relevant action."""
    entry_id: str
    timestamp: datetime
    actor_id: str            # user_id or "SYSTEM"
    action: AuditAction
    resource_type: str       # e.g. "profile", "loan", "consent"
    resource_id: str         # ID of the affected resource
    profile_id: str          # borrower whose data was affected
    details: dict = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    success: bool = True


def create_audit_entry(
    actor_id: str,
    action: AuditAction,
    resource_type: str,
    resource_id: str,
    profile_id: str,
    *,
    details: dict | None = None,
    ip_address: str = "",
    user_agent: str = "",
    success: bool = True,
) -> AuditEntry:
    return AuditEntry(
        entry_id=generate_id(),
        timestamp=datetime.now(UTC),
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        profile_id=profile_id,
        details=details or {},
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
    )


# ===========================================================================
# Data Lineage Record (Req 9.4)
# ===========================================================================
@dataclass
class DataLineageRecord:
    """Tracks data flow: where data came from, who accessed it, what was done."""
    record_id: str
    timestamp: datetime
    profile_id: str
    data_category: DataCategory
    source_service: str       # originating service
    target_service: str       # consuming service
    action: str               # e.g. "read", "transform", "share"
    fields_accessed: list[str] = field(default_factory=list)
    purpose: str = ""
    consent_id: str = ""      # link to the consent that authorized this access
    actor_id: str = ""


def create_lineage_record(
    profile_id: str,
    data_category: DataCategory,
    source_service: str,
    target_service: str,
    action: str,
    *,
    fields_accessed: list[str] | None = None,
    purpose: str = "",
    consent_id: str = "",
    actor_id: str = "",
) -> DataLineageRecord:
    return DataLineageRecord(
        record_id=generate_id(),
        timestamp=datetime.now(UTC),
        profile_id=profile_id,
        data_category=data_category,
        source_service=source_service,
        target_service=target_service,
        action=action,
        fields_accessed=fields_accessed or [],
        purpose=purpose,
        consent_id=consent_id,
        actor_id=actor_id,
    )


# ===========================================================================
# Retention Policy (Req 9.5)
# ===========================================================================
@dataclass
class RetentionPolicy:
    """Defines how long data of a specific category is retained."""
    policy_id: str
    data_category: DataCategory
    retention_days: int
    action: RetentionAction     # what to do when retention expires
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self, data_created_at: datetime) -> bool:
        """Check if data created at the given time has exceeded retention."""
        age = datetime.now(UTC) - data_created_at
        return age.days > self.retention_days


# Default retention policies for rural credit system
DEFAULT_RETENTION_POLICIES: list[dict] = [
    {
        "data_category": DataCategory.PERSONAL_IDENTITY,
        "retention_days": 2555,   # ~7 years (RBI KYC norms)
        "action": RetentionAction.DELETE,
        "description": "Personal identity data per RBI KYC norms",
    },
    {
        "data_category": DataCategory.FINANCIAL,
        "retention_days": 2555,   # ~7 years (Income Tax Act record keeping)
        "action": RetentionAction.ANONYMIZE,
        "description": "Financial records per IT Act requirements",
    },
    {
        "data_category": DataCategory.RISK_ASSESSMENT,
        "retention_days": 1095,   # ~3 years
        "action": RetentionAction.ANONYMIZE,
        "description": "Risk scores and factors",
    },
    {
        "data_category": DataCategory.CASH_FLOW,
        "retention_days": 1095,   # ~3 years
        "action": RetentionAction.ANONYMIZE,
        "description": "Cash flow forecast data",
    },
    {
        "data_category": DataCategory.GUIDANCE,
        "retention_days": 730,    # ~2 years
        "action": RetentionAction.DELETE,
        "description": "Credit guidance recommendations",
    },
    {
        "data_category": DataCategory.ALERT,
        "retention_days": 365,    # 1 year
        "action": RetentionAction.DELETE,
        "description": "Early warning alerts",
    },
    {
        "data_category": DataCategory.LOCATION,
        "retention_days": 1825,   # ~5 years
        "action": RetentionAction.ANONYMIZE,
        "description": "Location data",
    },
]


def build_default_retention_policies() -> list[RetentionPolicy]:
    """Create the standard set of retention policies."""
    return [
        RetentionPolicy(
            policy_id=generate_id(),
            data_category=DataCategory(p["data_category"]),
            retention_days=p["retention_days"],
            action=RetentionAction(p["action"]),
            description=p["description"],
        )
        for p in DEFAULT_RETENTION_POLICIES
    ]


# ===========================================================================
# Data Usage Summary (Req 9.4 — borrower data visibility)
# ===========================================================================
@dataclass
class DataUsageSummary:
    """Provides borrowers with visibility into how their data is used."""
    profile_id: str
    active_consents: list[Consent]
    total_data_accesses: int
    services_with_access: list[str]
    data_categories_stored: list[DataCategory]
    last_accessed_at: datetime | None
    retention_policies: list[RetentionPolicy]
    pending_deletion_categories: list[DataCategory]


def build_data_usage_summary(
    profile_id: str,
    consents: list[Consent],
    lineage_records: list[DataLineageRecord],
    retention_policies: list[RetentionPolicy],
) -> DataUsageSummary:
    """Build a summary of how a borrower's data is being used (Req 9.4)."""
    active_consents = [c for c in consents if c.is_active()]
    services = sorted({r.target_service for r in lineage_records})
    categories = sorted({r.data_category for r in lineage_records})
    last_accessed = (
        max((r.timestamp for r in lineage_records), default=None)
    )

    # Check which data categories are pending deletion
    pending = []
    if lineage_records:
        earliest_by_category: dict[DataCategory, datetime] = {}
        for r in lineage_records:
            if r.data_category not in earliest_by_category:
                earliest_by_category[r.data_category] = r.timestamp
            else:
                earliest_by_category[r.data_category] = min(
                    earliest_by_category[r.data_category], r.timestamp,
                )
        for policy in retention_policies:
            if policy.data_category in earliest_by_category and policy.is_expired(
                earliest_by_category[policy.data_category],
            ):
                pending.append(policy.data_category)

    return DataUsageSummary(
        profile_id=profile_id,
        active_consents=active_consents,
        total_data_accesses=len(lineage_records),
        services_with_access=services,
        data_categories_stored=[DataCategory(c) for c in categories],
        last_accessed_at=last_accessed,
        retention_policies=retention_policies,
        pending_deletion_categories=pending,
    )
