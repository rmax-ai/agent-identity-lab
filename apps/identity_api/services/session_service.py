"""Session creation and management service."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from apps.identity_api.repositories.agent_repo import AgentRepository
from packages.attestation.models import RuntimeAttestation
from packages.attestation.verifier import AttestationVerifier
from packages.common.enums import AgentStatus, BlueprintStatus, VerificationResult
from packages.common.settings import Settings
from packages.identity_models.delegation import DelegationGrant
from packages.identity_models.session import AgentSession
from packages.token_library.issuer import issue_session_token


class SessionError(Exception):
    pass


class SessionService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.db = session
        self.settings = settings

    async def create_session(
        self,
        agent_id: uuid.UUID,
        acting_user_id: str | None,
        delegation_grant_id: uuid.UUID | None,
        requested_scopes: list[str],
        requested_ttl_seconds: int,
        model_id: str,
        prompt_version: str,
        attestation_data: dict,
        attestation_signature: str,
    ) -> tuple[AgentSession, str]:
        """Create an agent session and return the session plus JWT."""
        repo = AgentRepository(self.db)
        agent = await repo.get_by_id(agent_id)
        if not agent:
            raise SessionError("Agent not found")
        if agent.status != AgentStatus.ACTIVE:
            raise SessionError(f"Agent is not active (status: {agent.status})")
        if not agent.public_key:
            raise SessionError("Agent has no registered public key")
        if not agent.blueprint or agent.blueprint.status != BlueprintStatus.ACTIVE:
            raise SessionError("Agent blueprint is not active")

        result, reason = AttestationVerifier.verify(
            attestation_data,
            attestation_signature,
            agent.public_key,
            str(agent_id),
        )
        if result != VerificationResult.VERIFIED:
            raise SessionError(f"Attestation rejected: {reason}")

        attestation = RuntimeAttestation(
            agent_id=agent_id,
            container_digest=attestation_data["container_digest"],
            git_commit=attestation_data["git_commit"],
            environment=attestation_data["environment"],
            host_id=attestation_data["host_id"],
            framework=attestation_data["framework"],
            framework_version=attestation_data["framework_version"],
            model_id=attestation_data.get("model", model_id),
            prompt_version=attestation_data.get("prompt_version", prompt_version),
            nonce=attestation_data["nonce"],
            signature=attestation_signature,
            issued_at=datetime.fromisoformat(attestation_data["issued_at"].replace("Z", "+00:00")),
            verified_at=datetime.now(UTC),
            verification_result=VerificationResult.VERIFIED,
        )
        self.db.add(attestation)
        await self.db.flush()

        if delegation_grant_id:
            delegation = await self.db.get(DelegationGrant, delegation_grant_id)
            if not delegation:
                raise SessionError("Delegation grant not found")
            if delegation.revoked_at:
                raise SessionError("Delegation grant has been revoked")
            if delegation.expires_at < datetime.now(UTC):
                raise SessionError("Delegation grant has expired")
            if delegation.agent_id != agent_id:
                raise SessionError("Delegation grant does not match agent")

        effective_scopes = requested_scopes
        ttl = min(
            requested_ttl_seconds,
            self.settings.session_max_ttl_seconds,
            agent.blueprint.max_session_ttl_seconds,
        )

        now = datetime.now(UTC)
        session = AgentSession(
            agent_id=agent_id,
            acting_user_id=acting_user_id,
            delegation_grant_id=delegation_grant_id,
            model_id=model_id,
            prompt_version=prompt_version,
            runtime_attestation_id=attestation.id,
            requested_scopes=requested_scopes,
            effective_scopes=effective_scopes,
            policy_version="0.1.0",
            trace_id=f"trace_{uuid.uuid4().hex[:16]}",
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl),
        )
        self.db.add(session)
        await self.db.flush()

        token = issue_session_token(
            session,
            self.settings,
            blueprint_id=f"{agent.blueprint.slug}:v{agent.blueprint.version}",
        )
        return session, token

    async def revoke_session(self, session_id: uuid.UUID) -> AgentSession:
        session = await self.db.get(AgentSession, session_id)
        if not session:
            raise SessionError("Session not found")
        if session.revoked_at:
            raise SessionError("Session already revoked")
        session.revoked_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(session)
        return session
