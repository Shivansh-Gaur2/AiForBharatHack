"""FastAPI routes for the Security & Privacy service.

Covers consent management, audit logging, data lineage, retention policies,
and data usage visibility for borrowers.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..domain.models import AuditEntry, Consent, DataLineageRecord
from ..domain.services import SecurityService
from .schemas import (
    AuditEntryDTO,
    AuditLogDTO,
    ConsentCheckDTO,
    ConsentCheckRequest,
    ConsentDTO,
    ConsentListDTO,
    DataAccessRequest,
    DataUsageSummaryDTO,
    GrantConsentRequest,
    LineageListDTO,
    LineageRecordDTO,
    LineageRequest,
    RetentionCheckDTO,
    RetentionCheckRequest,
    RetentionPolicyDTO,
    RetentionPolicyListDTO,
    RevokeConsentRequest,
)

router = APIRouter(prefix="/api/v1/security", tags=["Security & Privacy"])

# ---------------------------------------------------------------------------
# Service injection
# ---------------------------------------------------------------------------
_security_service: SecurityService | None = None


def set_security_service(svc: SecurityService) -> None:
    global _security_service
    _security_service = svc


def get_security_service() -> SecurityService:
    if _security_service is None:
        raise RuntimeError("SecurityService not initialised")
    return _security_service


# ---------------------------------------------------------------------------
# DTO converters
# ---------------------------------------------------------------------------
def _consent_to_dto(c: Consent) -> ConsentDTO:
    return ConsentDTO(
        consent_id=c.consent_id,
        profile_id=c.profile_id,
        purpose=c.purpose.value,
        status=c.status.value,
        granted_at=c.granted_at,
        expires_at=c.expires_at,
        revoked_at=c.revoked_at,
        granted_by=c.granted_by,
        revocation_reason=c.revocation_reason,
        version=c.version,
    )


def _audit_to_dto(e: AuditEntry) -> AuditEntryDTO:
    return AuditEntryDTO(
        entry_id=e.entry_id,
        timestamp=e.timestamp,
        actor_id=e.actor_id,
        action=e.action.value,
        resource_type=e.resource_type,
        resource_id=e.resource_id,
        profile_id=e.profile_id,
        details=e.details,
        success=e.success,
    )


def _lineage_to_dto(r: DataLineageRecord) -> LineageRecordDTO:
    return LineageRecordDTO(
        record_id=r.record_id,
        timestamp=r.timestamp,
        profile_id=r.profile_id,
        data_category=r.data_category.value,
        source_service=r.source_service,
        target_service=r.target_service,
        action=r.action,
        fields_accessed=r.fields_accessed,
        purpose=r.purpose,
        consent_id=r.consent_id,
    )


# ---------------------------------------------------------------------------
# Consent Routes (Req 9.3)
# ---------------------------------------------------------------------------
@router.post("/consent", response_model=ConsentDTO, status_code=201)
async def grant_consent(req: GrantConsentRequest):
    """Grant consent for a specific data-use purpose."""
    svc = get_security_service()
    try:
        consent = await svc.grant_consent(
            profile_id=req.profile_id,
            purpose=req.purpose,
            granted_by=req.granted_by,
            duration_days=req.duration_days,
        )
        return _consent_to_dto(consent)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/consent/{consent_id}/revoke", response_model=ConsentDTO)
async def revoke_consent(consent_id: str, req: RevokeConsentRequest):
    """Revoke a previously granted consent."""
    svc = get_security_service()
    try:
        consent = await svc.revoke_consent(
            consent_id=consent_id,
            reason=req.reason,
            revoked_by=req.revoked_by,
        )
        return _consent_to_dto(consent)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.get("/consent/{consent_id}", response_model=ConsentDTO)
async def get_consent(consent_id: str):
    """Get a specific consent record."""
    svc = get_security_service()
    consent = await svc.get_consent(consent_id)
    if consent is None:
        raise HTTPException(status_code=404, detail="Consent not found")
    return _consent_to_dto(consent)


@router.get("/consent/profile/{profile_id}", response_model=ConsentListDTO)
async def get_profile_consents(profile_id: str):
    """Get all consent records for a profile."""
    svc = get_security_service()
    consents = await svc.get_profile_consents(profile_id)
    return ConsentListDTO(
        items=[_consent_to_dto(c) for c in consents],
        count=len(consents),
    )


@router.post("/consent/check", response_model=ConsentCheckDTO)
async def check_consent(req: ConsentCheckRequest):
    """Check if active consent exists for a purpose."""
    svc = get_security_service()
    has_consent = await svc.check_consent(req.profile_id, req.purpose)
    return ConsentCheckDTO(
        profile_id=req.profile_id,
        purpose=req.purpose,
        has_consent=has_consent,
    )


# ---------------------------------------------------------------------------
# Audit Log Routes
# ---------------------------------------------------------------------------
@router.post("/audit/access", response_model=AuditEntryDTO, status_code=201)
async def log_data_access(req: DataAccessRequest):
    """Log a data access event for audit trail."""
    svc = get_security_service()
    entry = await svc.log_data_access(
        actor_id=req.actor_id,
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        profile_id=req.profile_id,
        details=req.details,
        ip_address=req.ip_address,
    )
    return _audit_to_dto(entry)


@router.get("/audit/profile/{profile_id}", response_model=AuditLogDTO)
async def get_audit_log(
    profile_id: str,
    limit: int = Query(50, ge=1, le=1000),
):
    """Get audit log entries for a profile."""
    svc = get_security_service()
    entries = await svc.get_audit_log(profile_id, limit)
    return AuditLogDTO(
        items=[_audit_to_dto(e) for e in entries],
        count=len(entries),
    )


# ---------------------------------------------------------------------------
# Data Lineage Routes (Req 9.4)
# ---------------------------------------------------------------------------
@router.post("/lineage", response_model=LineageRecordDTO, status_code=201)
async def record_lineage(req: LineageRequest):
    """Record a data lineage event."""
    svc = get_security_service()
    try:
        record = await svc.record_data_access(
            profile_id=req.profile_id,
            data_category=req.data_category,
            source_service=req.source_service,
            target_service=req.target_service,
            action=req.action,
            fields_accessed=req.fields_accessed,
            purpose=req.purpose,
            consent_id=req.consent_id,
            actor_id=req.actor_id,
        )
        return _lineage_to_dto(record)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/lineage/profile/{profile_id}", response_model=LineageListDTO)
async def get_lineage(
    profile_id: str,
    category: str | None = Query(None),
):
    """Get data lineage records for a profile, optionally filtered by category."""
    svc = get_security_service()
    try:
        records = await svc.get_data_lineage(profile_id, category)
        return LineageListDTO(
            items=[_lineage_to_dto(r) for r in records],
            count=len(records),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


# ---------------------------------------------------------------------------
# Data Usage Summary — borrower visibility (Req 9.4)
# ---------------------------------------------------------------------------
@router.get("/usage/{profile_id}", response_model=DataUsageSummaryDTO)
async def get_data_usage_summary(profile_id: str):
    """Get a complete summary of how a borrower's data is used."""
    svc = get_security_service()
    summary = await svc.get_data_usage_summary(profile_id)
    return DataUsageSummaryDTO(
        profile_id=summary.profile_id,
        active_consent_count=len(summary.active_consents),
        active_consents=[_consent_to_dto(c) for c in summary.active_consents],
        total_data_accesses=summary.total_data_accesses,
        services_with_access=summary.services_with_access,
        data_categories_stored=[c.value for c in summary.data_categories_stored],
        last_accessed_at=summary.last_accessed_at,
        pending_deletion_categories=[c.value for c in summary.pending_deletion_categories],
        retention_policies=[
            RetentionPolicyDTO(
                policy_id=p.policy_id,
                data_category=p.data_category.value,
                retention_days=p.retention_days,
                action=p.action.value,
                description=p.description,
                is_active=p.is_active,
            )
            for p in summary.retention_policies
        ],
    )


# ---------------------------------------------------------------------------
# Retention Policy Routes (Req 9.5)
# ---------------------------------------------------------------------------
@router.get("/retention/policies", response_model=RetentionPolicyListDTO)
async def get_retention_policies():
    """Get all retention policies."""
    svc = get_security_service()
    policies = await svc.get_retention_policies()
    return RetentionPolicyListDTO(
        items=[
            RetentionPolicyDTO(
                policy_id=p.policy_id,
                data_category=p.data_category.value,
                retention_days=p.retention_days,
                action=p.action.value,
                description=p.description,
                is_active=p.is_active,
            )
            for p in policies
        ],
        count=len(policies),
    )


@router.post("/retention/check", response_model=RetentionCheckDTO)
async def check_retention(req: RetentionCheckRequest):
    """Check if data has exceeded its retention period."""
    svc = get_security_service()
    try:
        result = await svc.check_retention_expired(
            profile_id=req.profile_id,
            data_category=req.data_category,
            data_created_at_iso=req.data_created_at,
        )
        return RetentionCheckDTO(**result)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/retention/initialize", response_model=RetentionPolicyListDTO)
async def initialize_policies():
    """Initialize default retention policies (idempotent)."""
    svc = get_security_service()
    policies = await svc.initialize_default_policies()
    return RetentionPolicyListDTO(
        items=[
            RetentionPolicyDTO(
                policy_id=p.policy_id,
                data_category=p.data_category.value,
                retention_days=p.retention_days,
                action=p.action.value,
                description=p.description,
                is_active=p.is_active,
            )
            for p in policies
        ],
        count=len(policies),
    )
