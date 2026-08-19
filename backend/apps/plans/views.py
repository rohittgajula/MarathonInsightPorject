from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.athletes.mixins import AthleteScopedMixin
from apps.athletes.permissions import IsAthleteOwner

from . import schedule as schedule_module
from .models import Race
from .serializers import RaceSerializer

# What each mode means in one line, for a reader looking at their own calendar. The
# per-day `mode_reason` explains a single date; this explains the shape.
MODE_LABELS = {
    "race": "Race day",
    "recovery": "Recovery",
    "mini_taper": "Taper",
    "maintenance": "Maintenance",
    "build": "Building",
    "off_season": "No race ahead",
}


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

    @action(detail=False, methods=["get"])
    def schedule(self, request):
        """The whole race calendar, resolved into the blocks it actually produces.

        Adding a second race changes the plan in ways no single race row can show:
        the days after the first race become recovery, the gap becomes maintenance
        or a build depending on how much room there is, and the days before the
        second become a taper. This is that answer, so the athlete can see what a
        date change did before living through it.
        """
        athlete = self.athlete
        today = athlete.local_today
        sched = schedule_module.for_athlete(athlete)
        start, end = schedule_module.span(sched, today)
        anchor = sched.anchor(today)
        ctx = sched.context(today)

        return Response({
            "today": today,
            "anchor_date": anchor.date if anchor else None,
            "current": {
                "mode": ctx.mode,
                "label": MODE_LABELS.get(ctx.mode, ctx.mode),
                "reason": ctx.reason,
                "weeks_out": ctx.weeks_out,
            },
            "blocks": [
                {
                    "mode": b.mode,
                    "label": MODE_LABELS.get(b.mode, b.mode),
                    "start": b.start, "end": b.end, "days": b.days,
                    "race_name": b.race.name if b.race else "",
                    "race_date": b.race.date if b.race else None,
                    "is_current": b.start <= today <= b.end,
                    "reason": b.reason,
                }
                for b in schedule_module.timeline(sched, start, end)
            ],
        })
