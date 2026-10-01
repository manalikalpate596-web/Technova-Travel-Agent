from datetime import timedelta

from .models import DependencyImpact, FlightDisruption, Itinerary


class DependencyAnalysisAgent:
    """Finds downstream events whose current slot no longer follows arrival."""

    def analyze(
        self,
        original: Itinerary,
        disrupted: Itinerary,
        disruption: FlightDisruption,
        transfer_buffer: timedelta,
    ) -> tuple[DependencyImpact, ...]:
        required_after = disruption.new_arrival + transfer_buffer
        impacted: list[DependencyImpact] = []

        for event in original.events:
            if event.id == disruption.flight_id:
                continue
            if not self._depends_on(original, event.id, disruption.flight_id):
                continue
            if event.start < required_after:
                impacted.append(
                    DependencyImpact(
                        event_id=event.id,
                        reason=(
                            f"Depends on {disruption.flight_id}; its scheduled start "
                            f"{event.start:%Y-%m-%d %H:%M} is before arrival plus "
                            f"the {transfer_buffer} transfer buffer"
                        ),
                        required_after=required_after,
                    )
                )

        return tuple(impacted)

    @staticmethod
    def _depends_on(itinerary: Itinerary, event_id: str, ancestor_id: str) -> bool:
        visited: set[str] = set()
        pending = list(itinerary.event(event_id).dependencies)
        while pending:
            dependency_id = pending.pop()
            if dependency_id == ancestor_id:
                return True
            if dependency_id in visited:
                continue
            visited.add(dependency_id)
            pending.extend(itinerary.event(dependency_id).dependencies)
        return False