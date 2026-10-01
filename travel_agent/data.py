from datetime import datetime

from .models import Event, Itinerary


def default_itinerary() -> Itinerary:
    """Return a deterministic, fully simulated two-day itinerary."""
    return Itinerary(
        events=(
            Event(
                id="flight-1",
                title="Flight to Northstar City",
                kind="flight",
                start=datetime(2026, 10, 20, 8, 0),
                end=datetime(2026, 10, 20, 12, 0),
                location="Northstar Airport",
            ),
            Event(
                id="hotel-1",
                title="Hotel check-in",
                kind="hotel",
                start=datetime(2026, 10, 20, 14, 0),
                end=datetime(2026, 10, 20, 14, 30),
                location="Northstar Hotel",
                dependencies=("flight-1",),
                movable=True,
                earliest_start=datetime(2026, 10, 20, 12, 45),
                latest_start=datetime(2026, 10, 20, 20, 0),
            ),
            Event(
                id="meeting-1",
                title="Project kickoff meeting",
                kind="meeting",
                start=datetime(2026, 10, 20, 15, 0),
                end=datetime(2026, 10, 20, 16, 0),
                location="Northstar Office",
                dependencies=("flight-1",),
                movable=True,
                earliest_start=datetime(2026, 10, 20, 13, 0),
                latest_start=datetime(2026, 10, 21, 11, 0),
            ),
            Event(
                id="activity-1",
                title="Museum visit",
                kind="activity",
                start=datetime(2026, 10, 21, 10, 0),
                end=datetime(2026, 10, 21, 12, 0),
                location="City Museum",
            ),
        )
    )