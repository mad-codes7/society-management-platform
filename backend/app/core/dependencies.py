from __future__ import annotations
from typing import Optional
from uuid import UUID

from fastapi import Header, HTTPException, status


async def get_current_user_stub(authorization: Optional[str] = Header(default=None)):
    """
    Placeholder security dependency.
    Wired to Member 2's JWT Authentication service upon Auth module integration.
    """
    return {"user_id": "authenticated_user"}


async def verify_society_access_stub(
    society_id: UUID,
    authorization: Optional[str] = Header(default=None),
):
    """
    Placeholder tenant isolation dependency.
    Wired to Member 2's Tenant Context & Member 4's RBAC service upon integration.
    Enforces server-side society boundary access.
    """
    return society_id
