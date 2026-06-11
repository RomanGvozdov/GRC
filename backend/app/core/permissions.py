"""Модель дозволів RBAC.

Модулі × рівні (none < read < write < manage):
- read   — перегляд;
- write  — редагування призначених користувачеві об'єктів;
- manage — створення/видалення/повне редагування в модулі.

Вбудовані ролі мають фіксовані мапи дозволів. Кастомна роль (User.custom_role)
повністю заміщує мапу вбудованої ролі.
"""

from app.models import Role, User

MODULES = [
    "risks",
    "controls",
    "frameworks",
    "audits",
    "policies",
    "reports",
    "audit_log",
    "admin",  # користувачі, довідники, ролі, API-токени
]

LEVELS = ["none", "read", "write", "manage"]
_LEVEL_RANK = {level: rank for rank, level in enumerate(LEVELS)}

BUILTIN_PERMISSIONS: dict[str, dict[str, str]] = {
    Role.ADMIN.value: {module: "manage" for module in MODULES},
    Role.GRC_MANAGER.value: {
        "risks": "manage",
        "controls": "manage",
        "frameworks": "read",
        "audits": "manage",
        "policies": "manage",
        "reports": "read",
        "audit_log": "read",
        "admin": "none",
    },
    Role.EXECUTOR.value: {
        "risks": "write",
        "controls": "write",
        "frameworks": "read",
        "audits": "write",
        "policies": "read",
        "reports": "read",
        "audit_log": "none",
        "admin": "none",
    },
    Role.READER.value: {
        "risks": "read",
        "controls": "read",
        "frameworks": "read",
        "audits": "read",
        "policies": "read",
        "reports": "read",
        "audit_log": "read",
        "admin": "none",
    },
}


def effective_permissions(user: User) -> dict[str, str]:
    if user.custom_role_id and user.custom_role:
        custom = user.custom_role.permissions or {}
        return {module: custom.get(module, "none") for module in MODULES}
    base = BUILTIN_PERMISSIONS.get(user.role, BUILTIN_PERMISSIONS[Role.READER.value])
    return dict(base)


def has_permission(user: User, module: str, level: str) -> bool:
    granted = effective_permissions(user).get(module, "none")
    return _LEVEL_RANK[granted] >= _LEVEL_RANK[level]


def can_edit_entity(user: User, owner_id: int | None, module: str) -> bool:
    """manage — редагує будь-що в модулі; write — лише призначене собі."""
    if has_permission(user, module, "manage"):
        return True
    if has_permission(user, module, "write"):
        return owner_id == user.id
    return False
