from dataclasses import replace
from datetime import datetime, timedelta

from .models import (
    DependencyImpact,
    Event,
    FlightDisruption,
    Itinerary,
    ReplanningOutcome,
)


class ReplanningAgent:
    """Searches allowed event windows for a conflict-free schedule."""

    def __init__(self, transfer_buffer: timedelta, slot_minutes: int = 15) -> None:
        if transfer_buffer < timedelta(0):
            raise ValueError("transfer_buffer cannot be negative")
        if slot_minutes <= 0:
            raise ValueError("slot_minutes must be positive")
        self.slot_minutes = slot_minutes
        self.transfer_buffer = transfer_buffer
        self.slot = timedelta(minutes=slot_minutes)

    def replan(
        self,
        original: Itinerary,
        disrupted: Itinerary,
        disruption: FlightDisruption,
        impacts: tuple[DependencyImpact, ...],
    ) -> ReplanningOutcome:
        impacted_ids = {impact.event_id for impact in impacts}
        if not impacted_ids:
            return ReplanningOutcome(
                itinerary=disrupted,
                decisions=("No dependent event lost its feasible time slot; itinerary retained.",),
            )

        for event in original.events:
            if event.id in impacted_ids and not event.movable:
                return self._request_human(
                    original,
                    disrupted,
                    disruption.flight_id,
                    f"{event.title} is affected but marked non-movable; no safe automatic change was made.",
                )

        reservations = [
            event
            for event in disrupted.events
            if event.id != disruption.flight_id and event.id not in impacted_ids
        ]
        planned: dict[str, Event] = {}
        decisions: list[str] = []
        ordered_impacts = sorted(
            (original.event(event_id) for event_id in impacted_ids),
            key=lambda event: event.start,
        )

        for event in ordered_impacts:
            lower_bound = max(
                event.earliest_start or event.start,
                disruption.new_arrival + self.transfer_buffer,
            )
            for dependency_id in event.dependencies:
                dependency = planned.get(dependency_id)
                if dependency is not None:
                    lower_bound = max(lower_bound, dependency.end)

            upper_bound = event.latest_start or event.start
            candidate = max(event.start, lower_bound)
            candidate = self._round_up(candidate)
            while candidate <= upper_bound and self._conflicts(
                candidate, candidate + (event.end - event.start), reservations
            ):
                candidate += self.slot

            if candidate > upper_bound:
                return self._request_human(
                    original,
                    disrupted,
                    disruption.flight_id,
                    f"No conflict-free slot is available for {event.title} within its allowed window.",
                )

            updated_event = replace(
                event,
                start=candidate,
                end=candidate + (event.end - event.start),
                change_reason=(
                    f"Moved because the delayed flight arrives at "
                    f"{disruption.new_arrival:%Y-%m-%d %H:%M}; the event must start "
                    f"after arrival plus the {self.transfer_buffer} transfer buffer."
                ),
            )
            planned[event.id] = updated_event
            reservations.append(updated_event)
            decisions.append(
                f"Move {event.title} from {event.start:%Y-%m-%d %H:%M} "
                f"to {updated_event.start:%Y-%m-%d %H:%M} to preserve the dependency and avoid overlap."
            )

        updated_events = tuple(
            planned.get(event.id, event) for event in disrupted.events
        )
        return ReplanningOutcome(
            itinerary=disrupted.with_events(updated_events),
            decisions=tuple(decisions),
        )

    def _round_up(self, value: datetime) -> datetime:
        remainder = value.minute % self.slot_minutes
        if remainder == 0 and value.second == 0 and value.microsecond == 0:
            return value
        return value.replace(second=0, microsecond=0) + timedelta(
            minutes=self.slot_minutes - remainder
        )

    @staticmethod
    def _conflicts(start: datetime, end: datetime, events: list[Event]) -> bool:
        return any(start < event.end and event.start < end for event in events)

    @staticmethod
    def _request_human(
        original: Itinerary, disrupted: Itinerary, flight_id: str, reason: str
    ) -> ReplanningOutcome:
        flight = disrupted.event(flight_id)
        result = original.with_events(
            tuple(flight if event.id == flight.id else event for event in original.events)
        )
        return ReplanningOutcome(
            itinerary=result,
            decisions=("Automatic replan stopped; original non-flight events were retained.",),
            needs_human_intervention=True,
            intervention_reason=reason,
        )