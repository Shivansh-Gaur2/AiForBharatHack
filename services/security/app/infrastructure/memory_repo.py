"""In-memory repository implementation for the Security & Privacy service.

A single class that satisfies all four repository protocol contracts:
  - ConsentRepository
  - AuditRepository
  - DataLineageRepository
  - RetentionPolicyRepository

Default storage backend for local development and testing — no AWS needed.
"""

from __future__ import annotations

from services.security.app.domain.auth_models import User
from services.security.app.domain.models import (
    AuditEntry,
    Consent,
    ConsentPurpose,
    ConsentStatus,
    DataCategory,
    DataLineageRecord,
    RetentionPolicy,
)


class InMemorySecurityRepository:
    """Thread-unsafe in-memory store; suitable for single-process local dev.

    Implements all four port protocols from domain/interfaces.py.
    """

    def __init__(self) -> None:
        # ------ Consent ------
        self._consents: dict[str, Consent] = {}
        # profile_id → list[consent_id]
        self._consents_by_profile: dict[str, list[str]] = {}

        # ------ Audit ------
        self._audit_entries: dict[str, AuditEntry] = {}
        # profile_id → list[entry_id]  (insertion order)
        self._audit_by_profile: dict[str, list[str]] = {}
        # actor_id → list[entry_id]
        self._audit_by_actor: dict[str, list[str]] = {}
        # action → list[entry_id]
        self._audit_by_action: dict[str, list[str]] = {}

        # ------ Data Lineage ------
        self._lineage: dict[str, DataLineageRecord] = {}
        # profile_id → list[record_id]
        self._lineage_by_profile: dict[str, list[str]] = {}

        # ------ Retention Policies ------
        self._policies: dict[str, RetentionPolicy] = {}
        # DataCategory value → policy_id
        self._policy_by_category: dict[str, str] = {}

        # ------ Users (AuthService) ------
        self._users: dict[str, User] = {}
        # email (lowercased) → user_id
        self._users_by_email: dict[str, str] = {}

    # ======================================================================
    # ConsentRepository
    # ======================================================================

    async def save_consent(self, consent: Consent) -> None:
        self._consents[consent.consent_id] = consent
        bucket = self._consents_by_profile.setdefault(consent.profile_id, [])
        if consent.consent_id not in bucket:
            bucket.append(consent.consent_id)

    async def find_consent_by_id(self, consent_id: str) -> Consent | None:
        return self._consents.get(consent_id)

    async def find_consents_by_profile(self, profile_id: str) -> list[Consent]:
        ids = self._consents_by_profile.get(profile_id, [])
        return [self._consents[cid] for cid in ids if cid in self._consents]

    async def find_active_consent(
        self, profile_id: str, purpose: ConsentPurpose,
    ) -> Consent | None:
        for cid in reversed(self._consents_by_profile.get(profile_id, [])):
            c = self._consents.get(cid)
            if c and c.purpose == purpose and c.status == ConsentStatus.GRANTED:
                return c
        return None

    async def update_consent(self, consent: Consent) -> None:
        self._consents[consent.consent_id] = consent

    async def delete_by_profile(self, profile_id: str) -> int:
        ids = self._consents_by_profile.pop(profile_id, [])
        for cid in ids:
            self._consents.pop(cid, None)
        return len(ids)

    # ======================================================================
    # AuditRepository
    # ======================================================================

    async def save_entry(self, entry: AuditEntry) -> None:
        self._audit_entries[entry.entry_id] = entry
        self._audit_by_profile.setdefault(entry.profile_id, []).append(entry.entry_id)
        self._audit_by_actor.setdefault(entry.actor_id, []).append(entry.entry_id)
        self._audit_by_action.setdefault(entry.action, []).append(entry.entry_id)

    async def find_entries_by_profile(
        self, profile_id: str, limit: int = 50,
    ) -> list[AuditEntry]:
        ids = self._audit_by_profile.get(profile_id, [])
        recent = ids[-limit:][::-1]
        return [self._audit_entries[eid] for eid in recent if eid in self._audit_entries]

    async def find_entries_by_actor(
        self, actor_id: str, limit: int = 50,
    ) -> list[AuditEntry]:
        ids = self._audit_by_actor.get(actor_id, [])
        recent = ids[-limit:][::-1]
        return [self._audit_entries[eid] for eid in recent if eid in self._audit_entries]

    async def find_entries_by_action(
        self, action: str, limit: int = 50,
    ) -> list[AuditEntry]:
        ids = self._audit_by_action.get(action, [])
        recent = ids[-limit:][::-1]
        return [self._audit_entries[eid] for eid in recent if eid in self._audit_entries]

    # ======================================================================
    # DataLineageRepository
    # ======================================================================

    async def save_record(self, record: DataLineageRecord) -> None:
        self._lineage[record.record_id] = record
        self._lineage_by_profile.setdefault(record.profile_id, []).append(record.record_id)

    async def find_records_by_profile(
        self, profile_id: str, limit: int = 100,
    ) -> list[DataLineageRecord]:
        ids = self._lineage_by_profile.get(profile_id, [])
        recent = ids[-limit:]
        return [self._lineage[rid] for rid in recent if rid in self._lineage]

    async def find_records_by_category(
        self, profile_id: str, category: DataCategory,
    ) -> list[DataLineageRecord]:
        ids = self._lineage_by_profile.get(profile_id, [])
        return [
            self._lineage[rid]
            for rid in ids
            if rid in self._lineage
            and self._lineage[rid].data_category == category
        ]

    async def delete_by_profile(self, profile_id: str) -> int:
        ids = self._lineage_by_profile.pop(profile_id, [])
        for rid in ids:
            self._lineage.pop(rid, None)
        return len(ids)

    # ======================================================================
    # RetentionPolicyRepository
    # ======================================================================

    async def save_policy(self, policy: RetentionPolicy) -> None:
        self._policies[policy.policy_id] = policy
        self._policy_by_category[str(policy.data_category)] = policy.policy_id

    async def find_all_policies(self) -> list[RetentionPolicy]:
        return list(self._policies.values())

    async def find_policy_by_category(
        self, category: DataCategory,
    ) -> RetentionPolicy | None:
        pid = self._policy_by_category.get(str(category))
        if pid is None:
            return None
        return self._policies.get(pid)

    # ======================================================================
    # UserRepository  (used by AuthService)
    # ======================================================================

    async def save_user(self, user: User) -> None:
        self._users[user.user_id] = user
        self._users_by_email[user.email.lower()] = user.user_id

    async def find_user_by_id(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def find_user_by_email(self, email: str) -> User | None:
        uid = self._users_by_email.get(email.lower())
        if uid is None:
            return None
        return self._users.get(uid)

    async def update_user(self, user: User) -> None:
        """Persist a mutated User object (e.g. updated last_login_at)."""
        self._users[user.user_id] = user
        self._users_by_email[user.email.lower()] = user.user_id
