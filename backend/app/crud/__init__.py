"""Repository layer: persistence for each aggregate.

Keeps the original ``app.crud`` import path working while organizing DB access
per entity. Routes depend on this layer (and on ``core`` helpers), not on raw
SQLAlchemy sessions.
"""

from app.crud.api_keys import (
    create_api_key,
    find_by_key,
    get_api_key,
    list_api_keys,
    revoke_api_key,
)
from app.crud.audit import list_audit_logs, record_audit
from app.crud.items import (
    count_items,
    create_item,
    get_item,
    list_items,
)
from app.crud.notifications import (
    count_unread,
    create_notification,
    list_notifications,
    mark_all_read,
    mark_read,
)
from app.crud.organizations import (
    add_member,
    count_members,
    create_invite,
    create_organization,
    find_membership,
    get_invite_by_token,
    get_organization,
    get_pending_invite,
    list_invites,
    list_members,
    list_user_memberships,
    remove_member,
    update_member_role,
    update_organization,
)
from app.crud.sessions import (
    create_session,
    get_session,
    get_session_by_refresh_hash,
    list_active_sessions,
    revoke_session,
)
from app.crud.users import (
    authenticate,
    create_user,
    ensure_personal_organization,
    get_user_by_email,
    get_user_by_id,
    list_users,
    update_user,
)
from app.crud.webhooks import (
    create_delivery,
    create_webhook,
    get_webhook,
    list_active_webhooks_for_event,
    list_deliveries,
    list_webhooks,
    update_webhook,
)

__all__ = [
    "authenticate",
    "create_user",
    "update_user",
    "get_user_by_email",
    "get_user_by_id",
    "list_users",
    "ensure_personal_organization",
    "create_item",
    "get_item",
    "count_items",
    "list_items",
    "get_organization",
    "find_membership",
    "list_user_memberships",
    "create_organization",
    "update_organization",
    "list_members",
    "add_member",
    "update_member_role",
    "remove_member",
    "count_members",
    "create_invite",
    "get_invite_by_token",
    "get_pending_invite",
    "list_invites",
    "create_session",
    "get_session",
    "get_session_by_refresh_hash",
    "list_active_sessions",
    "revoke_session",
    "create_api_key",
    "find_by_key",
    "get_api_key",
    "list_api_keys",
    "revoke_api_key",
    "create_webhook",
    "get_webhook",
    "list_webhooks",
    "list_active_webhooks_for_event",
    "update_webhook",
    "create_delivery",
    "list_deliveries",
    "create_notification",
    "list_notifications",
    "count_unread",
    "mark_read",
    "mark_all_read",
    "record_audit",
    "list_audit_logs",
]
