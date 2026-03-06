from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from logs_sentinel.domains.identity.entities import Role
from logs_sentinel.domains.ingestion.entities import hash_ingest_token
from logs_sentinel.infrastructure.db.base import Base, SessionFactory, engine
from logs_sentinel.infrastructure.db.models import (
    IngestTokenModel,
    MembershipModel,
    ProjectModel,
    TenantModel,
    UserModel,
)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionFactory() as session:
        now = datetime.now(tz=timezone.utc)

        tenant = TenantModel(name="Acme Logs", created_at=now)
        user = UserModel(
            email="owner@example.com",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$ZGV2LXNhbHQ$K1tK5x",  # placeholder
            is_active=True,
            created_at=now,
        )
        session.add_all([tenant, user])
        await session.flush()

        membership = MembershipModel(
            tenant_id=tenant.id,
            user_id=user.id,
            role=Role.OWNER.value,
        )
        project = ProjectModel(tenant_id=tenant.id, name="Acme Backend", created_at=now)
        session.add_all([membership, project])
        await session.flush()

        raw_token = "dev-token-change-me"
        token = IngestTokenModel(
            tenant_id=tenant.id,
            project_id=project.id,
            token_hash=hash_ingest_token(raw_token),
            last_used_at=None,
            revoked_at=None,
        )
        session.add(token)
        await session.commit()

        print("Seeded tenant 'Acme Logs'")
        print("User: owner@example.com (set a real password in DB for dev)")
        print(f"Project: Acme Backend (id={project.id})")
        print(f"Ingestion token (use as X-Project-Token): {raw_token}")


if __name__ == "__main__":
    asyncio.run(main())
