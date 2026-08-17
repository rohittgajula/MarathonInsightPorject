from rest_framework.exceptions import PermissionDenied


class AthleteScopedMixin:
    """Scopes every queryset to the requesting user's athlete.

    Multi-tenant from the start: there is no code path that returns another
    athlete's rows, so adding a second runner never requires an audit.
    """

    athlete_lookup = "athlete"

    @property
    def athlete(self):
        athlete = getattr(self.request.user, "athlete", None)
        if athlete is None:
            raise PermissionDenied("No athlete profile for this user.")
        return athlete

    def get_queryset(self):
        return super().get_queryset().filter(**{self.athlete_lookup: self.athlete})
