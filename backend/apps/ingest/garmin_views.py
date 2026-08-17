import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .garmin import GarminAuthError, GarminRateLimited, check_connection, sync_athlete

logger = logging.getLogger(__name__)


def _athlete(request):
    athlete = getattr(request.user, "athlete", None)
    if athlete is None:
        raise PermissionDenied("No athlete profile.")
    return athlete


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def garmin_status(request):
    return Response(check_connection(_athlete(request)))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def garmin_sync(request):
    """Pull recent activities. Safe to press repeatedly — ingest is idempotent."""
    athlete = _athlete(request)
    limit = min(int(request.data.get("limit", 20)), 100)
    try:
        result = sync_athlete(athlete, limit=limit)
    except GarminRateLimited as exc:
        # 429 upward, so the UI can tell "wait" apart from "log in again".
        return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    except GarminAuthError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as exc:  # noqa: BLE001
        logger.exception("garmin sync failed")
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    return Response(result.as_dict())
