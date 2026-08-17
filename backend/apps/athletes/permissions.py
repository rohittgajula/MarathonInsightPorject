from rest_framework import permissions


class IsAthleteOwner(permissions.BasePermission):
    """Tenancy guard. Every queryset is already filtered by athlete; this is the
    second line of defence for object-level access."""

    def has_object_permission(self, request, view, obj):
        athlete = getattr(request.user, "athlete", None)
        if athlete is None:
            return False
        owner = getattr(obj, "athlete", None) or getattr(getattr(obj, "activity", None), "athlete", None)
        return owner == athlete
