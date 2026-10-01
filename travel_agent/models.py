from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Event:
    id: str
    title: str
    kind: str
    start: datetime
    end: datetime
    location: str
    dependencies: tuple[str, ...] = ()
    movable: bool = False
    earliest_start: datetime | None = None
    latest_start: datetime | None = None
    change_reason: str | None = None

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("Event end must be later than event start")
        if self.earliest_start and self.latest_start:
            if self.latest_start < self.earliest_start:
                raise ValueError("latest_start must not precede earliest_start")

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()


@dataclass(frozen=True)
class Itinerary:
    events: tuple[Event, ...]

    def __post_init__(self) -> None:
        identifiers = [event.id for event in self.events]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Event IDs must be unique")
        known_ids = set(identifiers)
        for event in self.events:
            missing = set(event.dependencies) - known_ids
            if missing:
                raise ValueError(f"Unknown dependencies for {event.id}: {sorted(missing)}")

    def event(self, event_id: str) -> Event:
        for event in self.events:
            if event.id == event_id:
                return event
        raise KeyError(f"Unknown itinerary event: {event_id}")

    def with_events(self, events: tuple[Event, ...]) -> Itinerary:
        return Itinerary(events=events)


@dataclass(frozen=True)
class DisruptionRequest:
    flight_id: str
    delay_by_seconds: int | None = None
    new_departure: datetime | None = None

    def __post_init__(self) -> None:
        if (self.delay_by_seconds is None) == (self.new_departure is None):
            raise ValueError("Provide exactly one of delay_by_seconds or new_departure")
        if self.delay_by_seconds is not None and self.delay_by_seconds < 0:
            raise ValueError("A simulated delay cannot be negative")


@dataclass(frozen=True)
class FlightDisruption:
    flight_id: str
    old_departure: datetime
    new_departure: datetime
    old_arrival: datetime
    new_arrival: datetime

    @property
    def description(self) -> str:
        if self.new_departure >= self.old_departure:
            delay = self.new_departure - self.old_departure
            return f"Departure delayed by {delay}"
        return f"Departure changed to {self.new_departure:%Y-%m-%d %H:%M}"


@dataclass(frozen=True)
class DependencyImpact:
    event_id: str
    reason: str
    required_after: datetime


@dataclass(frozen=True)
class ReplanningOutcome:
    itinerary: Itinerary
    decisions: tuple[str, ...] = field(default_factory=tuple)
    needs_human_intervention: bool = False
    intervention_reason: str | None = None


@dataclass(frozen=True)
class WorkflowResult:
    original_itinerary: Itinerary
    updated_itinerary: Itinerary
    disruption: FlightDisruption
    affected: tuple[DependencyImpact, ...]
    decisions: tuple[str, ...]
    tool_calls: tuple[str, ...]
    needs_human_intervention: bool = False
    intervention_reason: str | None = None
    agent_explanation: str | None = None
    fallback_reason: str | None = None