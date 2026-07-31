"""Organization domain rules: roles, permissions and slug helpers.

Persistence lives in the ``app.crud`` layer; this module only encodes policy.
"""

import re

from app.models import (
    ORG_ROLE_ADMIN,
    ORG_ROLE_MEMBER,
    ORG_ROLE_OWNER,
    ORG_ROLE_VIEWER,
)

# Per-tenant role -> permissions
ORG_ROLE_PERMISSIONS: dict[str, set[str]] = {
    ORG_ROLE_OWNER: {
        "org:view",
        "org:update",
        "org:delete",
        "member:invite",
        "member:manage",
        "member:remove",
        "billing:manage",
        "item:create",
        "item:read",
        "item:update",
        "item:delete",
    },
    ORG_ROLE_ADMIN: {
        "org:view",
        "org:update",
        "member:invite",
        "member:manage",
        "billing:manage",
        "item:create",
        "item:read",
        "item:update",
        "item:delete",
    },
    ORG_ROLE_MEMBER: {
        "org:view",
        "item:create",
        "item:read",
        "item:update",
    },
    ORG_ROLE_VIEWER: {
        "org:view",
        "item:read",
    },
}

ROLE_RANK = {
    ORG_ROLE_VIEWER: 1,
    ORG_ROLE_MEMBER: 2,
    ORG_ROLE_ADMIN: 3,
    ORG_ROLE_OWNER: 4,
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "org"


def has_permission(role: str, permission: str) -> bool:
    return permission in ORG_ROLE_PERMISSIONS.get(role, set())
