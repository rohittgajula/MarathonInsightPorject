from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import board, evaluate


def _athlete(request):
    athlete = getattr(request.user, "athlete", None)
    if athlete is None:
        raise PermissionDenied("No athlete profile.")
    return athlete


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def achievements(request):
    athlete = _athlete(request)
    # Evaluate on read so a newly synced activity shows its achievement immediately,
    # rather than waiting for a background pass.
    evaluate(athlete)
    return Response(board(athlete))
