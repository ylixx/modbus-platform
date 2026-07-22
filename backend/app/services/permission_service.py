"""Permission checking service."""
import json
from functools import wraps
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.permission import RolePermission, UserRole
from app.models.device import Device


def get_user_permissions(db: Session, user: User) -> set[str]:
    """Get all permission codes for a user (from all assigned roles)."""
    # Admin shortcut: legacy role field
    if user.role == "admin":
        return {"*"}  # wildcard = all permissions

    perms = set()
    user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    for ur in user_roles:
        role_perms = db.query(RolePermission).filter(RolePermission.role_id == ur.role_id).all()
        for rp in role_perms:
            perm = rp.permission
            if perm:
                perms.add(perm.code)
    return perms


def has_permission(user_permissions: set[str], required: str) -> bool:
    """Check if user has a specific permission."""
    if "*" in user_permissions:
        return True
    return required in user_permissions


def get_user_data_scope(db: Session, user: User) -> dict:
    """Get the merged data scope for a user.

    Returns:
        {"scope": "all"|"factory"|"workshop"|"self", "values": ["车间A", ...]}
    If user has multiple roles, the broadest scope wins.
    """
    if user.role == "admin":
        return {"scope": "all", "values": []}

    user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()

    # Broadest scope wins
    scope_priority = {"all": 3, "factory": 2, "workshop": 1, "self": 0}
    best_scope = "self"
    best_values = []

    for ur in user_roles:
        priority = scope_priority.get(ur.data_scope, 0)
        if priority > scope_priority.get(best_scope, 0):
            best_scope = ur.data_scope
            try:
                best_values = json.loads(ur.scope_values) if ur.scope_values else []
            except (json.JSONDecodeError, TypeError):
                best_values = []
        elif priority == scope_priority.get(best_scope, 0) and ur.data_scope == best_scope:
            # Merge values for same scope level
            try:
                extra = json.loads(ur.scope_values) if ur.scope_values else []
                best_values = list(set(best_values + extra))
            except (json.JSONDecodeError, TypeError):
                pass

    return {"scope": best_scope, "values": best_values}


def apply_data_scope_filter(query, model, db: Session, user: User):
    """Apply data scope filter to a SQLAlchemy query.

    Supports filtering on Device model by factory/workshop fields.
    """
    scope = get_user_data_scope(db, user)

    if scope["scope"] == "all":
        return query  # no filter

    if scope["scope"] == "factory" and scope["values"]:
        return query.filter(model.factory.in_(scope["values"]))

    if scope["scope"] == "workshop" and scope["values"]:
        return query.filter(model.workshop.in_(scope["values"]))

    if scope["scope"] == "self":
        # For devices: only devices created by this user (no creator field yet, return none)
        return query.filter(model.id == -1)  # empty result

    return query
