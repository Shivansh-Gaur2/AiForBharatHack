"""Pydantic request/response DTOs for the Security & Privacy API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------
class GrantConsentRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)
    purpose: str
    granted_by: str = ""
    duration_days: int = Field(365, ge=1, le=3650)


class RevokeConsentRequest(BaseModel):
    reason: str = ""
    revoked_by: str = ""


class DataAccessRequest(BaseModel):
    """Log a data access event."""
    actor_id: str = Field(..., min_length=1)
    resource_type: str = Field(..., min_length=1)
    resource_id: str = Field(..., min_length=1)
    profile_id: str = Field(..., min_length=1)
    details: dict | None = None
    ip_address: str = ""


class LineageRequest(BaseModel):
    """Record a data lineage event."""
    profile_id: str = Field(..., min_length=1)
    data_category: str
    source_service: str = Field(..., min_length=1)
    target_service: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    fields_accessed: list[str] = Field(default_factory=list)
    purpose: str = ""
    consent_id: str = ""
    actor_id: str = ""


class ConsentCheckRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)
    purpose: str


class RetentionCheckRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)
    data_category: str
    data_created_at: str  # ISO format datetime


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------
class ConsentDTO(BaseModel):
    consent_id: str
    profile_id: str
    purpose: str
    status: str
    granted_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    granted_by: str
    revocation_reason: str
    version: int


class ConsentListDTO(BaseModel):
    items: list[ConsentDTO]
    count: int


class ConsentCheckDTO(BaseModel):
    profile_id: str
    purpose: str
    has_consent: bool


class AuditEntryDTO(BaseModel):
    entry_id: str
    timestamp: datetime
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    profile_id: str
    details: dict
    success: bool


class AuditLogDTO(BaseModel):
    items: list[AuditEntryDTO]
    count: int


class LineageRecordDTO(BaseModel):
    record_id: str
    timestamp: datetime
    profile_id: str
    data_category: str
    source_service: str
    target_service: str
    action: str
    fields_accessed: list[str]
    purpose: str
    consent_id: str


class LineageListDTO(BaseModel):
    items: list[LineageRecordDTO]
    count: int


class RetentionPolicyDTO(BaseModel):
    policy_id: str
    data_category: str
    retention_days: int
    action: str
    description: str
    is_active: bool


class RetentionPolicyListDTO(BaseModel):
    items: list[RetentionPolicyDTO]
    count: int


class RetentionCheckDTO(BaseModel):
    expired: bool
    data_category: str
    retention_days: int
    action: str
    reason: str


class DataUsageSummaryDTO(BaseModel):
    profile_id: str
    active_consent_count: int
    active_consents: list[ConsentDTO]
    total_data_accesses: int
    services_with_access: list[str]
    data_categories_stored: list[str]
    last_accessed_at: datetime | None
    pending_deletion_categories: list[str]
    retention_policies: list[RetentionPolicyDTO]
