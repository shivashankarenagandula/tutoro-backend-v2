"""
accounts.permissions
----------------------
Shared role-based permission classes used across every app's views.
Kept in accounts (not duplicated per-app) since role checks always
key off the same User.role field.
"""

from rest_framework import permissions

from .models import User


class IsAdminRole(permissions.BasePermission):
    """Full staff/admin access — used for matching, verification, etc."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == User.Role.ADMIN or request.user.is_staff)
        )


class IsParentRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == User.Role.PARENT
        )


class IsTutorRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == User.Role.TUTOR
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level check: the object must have a `.user` (or `.user_id`)
    attribute matching request.user, OR the requester is admin/staff.
    Used on profile and request detail views so a parent can't read or
    edit another parent's data.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.role == User.Role.ADMIN or request.user.is_staff:
            return True
        owner_id = getattr(obj, "user_id", None) or getattr(getattr(obj, "user", None), "id", None)
        return owner_id == request.user.id
