from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.activities.models import Activity

from .models import Athlete
from .permissions import IsAthleteOwner
from .serializers import AthleteSerializer


class AthleteViewSet(viewsets.GenericViewSet):
    serializer_class = AthleteSerializer
    permission_classes = [IsAthleteOwner]
    queryset = Athlete.objects.all()

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        athlete = getattr(request.user, "athlete", None)
        if athlete is None:
            return Response({"detail": "No athlete profile."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "PATCH":
            serializer = self.get_serializer(athlete, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            # Pace band and cadence threshold feed the derived layer, so changing them
            # invalidates every stored metric for this athlete.
            if {"easy_pace_min", "easy_pace_max", "hr_ceiling",
                "run_cadence_threshold", "training_days"} & set(request.data):
                Activity.objects.filter(athlete=athlete).update(metrics_current=False)
            return Response(serializer.data)

        return Response(self.get_serializer(athlete).data)
