from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from argon2 import PasswordHasher

from logs_sentinel.domains.identity.entities import Role
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
        now = datetime.now(tz=UTC)

        tenant = TenantModel(name="Acme Logs", created_at=now)

        hasher = PasswordHasher()
        dev_password = "changeme!"
        password_hash = hasher.hash(dev_password)

        user = UserModel(
            email="owner@example.com",
            password_hash=password_hash,
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

        token = IngestTokenModel(
            tenant_id=tenant.id,
            project_id=project.id,
            token_hash="dev-token-change-me",
            last_used_at=None,
            revoked_at=None,
        )
        session.add(token)
        await session.commit()

        print("Seeded tenant 'Acme Logs'")
        print("User: owner@example.com")
        print(f"Password: {dev_password}")
        print(f"Project: Acme Backend (id={project.id})")
        print("Ingestion token (use as X-Project-Token): dev-token-change-me")


if __name__ == "__main__":
    asyncio.run(main())

