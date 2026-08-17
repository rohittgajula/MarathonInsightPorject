from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.athletes.mixins import AthleteScopedMixin
from apps.athletes.permissions import IsAthleteOwner

from .models import Race
from .serializers import RaceSerializer


class RaceViewSet(AthleteScopedMixin, viewsets.ModelViewSet):
    queryset = Race.objects.all()
    serializer_class = RaceSerializer
    permission_classes = [IsAthleteOwner]

    def perform_create(self, serializer):
        serializer.save(athlete=self.athlete)

    @action(detail=False, methods=["get"])
    def target(self, request):
        """The race currently driving the plan, if one is set."""
        race = self.get_queryset().filter(is_target=True).first()
        if race is None:
            return Response(None)
        return Response(self.get_serializer(race).data)
