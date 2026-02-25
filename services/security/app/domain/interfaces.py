"""Port interfaces for the Security & Privacy service.

These Protocol classes define the contracts that infrastructure adapters
must implement, keeping the domain layer free of framework dependencies.
"""

from __future__ import annotations

from typing import Protocol

from .models import (
    AuditEntry,
    Consent,
    ConsentPurpose,
    DataCategory,
    DataLineageRecord,
    RetentionPolicy,
)


class ConsentRepository(Protocol):
    """Persistence port for consent records."""

    async def save_consent(self, consent: Consent) -> None: ...

    async def find_consent_by_id(self, consent_id: str) -> Consent | None: ...

    async def find_consents_by_profile(
        self, profile_id: str,
    ) -> list[Consent]: ...

    async def find_active_consent(
        self, profile_id: str, purpose: ConsentPurpose,
    ) -> Consent | None: ...

    async def update_consent(self, consent: Consent) -> None: ...


class AuditRepository(Protocol):
    """Persistence port for audit log entries."""

    async def save_entry(self, entry: AuditEntry) -> None: ...

    async def find_entries_by_profile(
        self, profile_id: str, limit: int = 50,
    ) -> list[AuditEntry]: ...

    async def find_entries_by_actor(
        self, actor_id: str, limit: int = 50,
    ) -> list[AuditEntry]: ...

    async def find_entries_by_action(
        self, action: str, limit: int = 50,
    ) -> list[AuditEntry]: ...


class DataLineageRepository(Protocol):
    """Persistence port for data lineage records."""

    async def save_record(self, record: DataLineageRecord) -> None: ...

    async def find_records_by_profile(
        self, profile_id: str, limit: int = 100,
    ) -> list[DataLineageRecord]: ...

    async def find_records_by_category(
        self, profile_id: str, category: DataCategory,
    ) -> list[DataLineageRecord]: ...


class RetentionPolicyRepository(Protocol):
    """Persistence port for retention policies."""

    async def save_policy(self, policy: RetentionPolicy) -> None: ...

    async def find_all_policies(self) -> list[RetentionPolicy]: ...

    async def find_policy_by_category(
        self, category: DataCategory,
    ) -> RetentionPolicy | None: ...
