"""Permisos del panel de administración: acceso por módulo.

Cada usuario aprobado tiene una lista de módulos. Un superadministrador tiene
todos los módulos y además puede dar o quitar el permiso de superadministrador.
"""

# Clave del módulo -> nombre visible. El orden es el que se muestra en el panel.
MODULES = {
    "programs": "Programas",
    "students": "Estudiantes",
    "groups": "Grupos",
    "assignments": "Asignaciones",
    "weekend": "Fin de semana",
    "sound": "Sonido",
    "talks": "Conferencias",
    "reports": "Informes de predicación",
    "users": "Usuarios y permisos",
}
ALL_MODULES = list(MODULES)

STATUS_PENDING = "pending"    # se registró y espera aprobación
STATUS_ACTIVE = "active"      # puede entrar al panel
STATUS_DISABLED = "disabled"  # un administrador le quitó el acceso
STATUSES = (STATUS_PENDING, STATUS_ACTIVE, STATUS_DISABLED)


def clean_permissions(perms) -> list[str]:
    """Deja solo módulos conocidos, sin repetir y en el orden del panel."""
    wanted = set(perms or [])
    return [m for m in ALL_MODULES if m in wanted]


def effective_permissions(user) -> list[str]:
    if user.is_superadmin:
        return list(ALL_MODULES)
    return clean_permissions(user.permissions)


def has_permission(user, module: str) -> bool:
    return user.is_superadmin or module in (user.permissions or [])
