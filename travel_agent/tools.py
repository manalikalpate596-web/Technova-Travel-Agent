from dataclasses import replace
from datetime import timedelta

from .models import DisruptionRequest, FlightDisruption, Itinerary


class SimulatedFlightDisruptionTool:
    """Changes a simulated flight while preserving its scheduled duration."""

    def apply(
        self, itinerary: Itinerary, request: DisruptionRequest
    ) -> tuple[Itinerary, FlightDisruption]:
        flight = itinerary.event(request.flight_id)
        if flight.kind != "flight":
            raise ValueError(f"Event {flight.id} is not a flight")

        departure = request.new_departure
        if request.delay_by_seconds is not None:
            departure = flight.start + timedelta(seconds=request.delay_by_seconds)
        assert departure is not None
        shift = departure - flight.start
        updated_flight = replace(
            flight,
            start=departure,
            end=flight.end + shift,
            change_reason=(
                f"Simulated disruption changed departure from "
                f"{flight.start:%Y-%m-%d %H:%M} to {departure:%Y-%m-%d %H:%M}; "
                "flight duration was preserved."
            ),
        )
        updated = itinerary.with_events(
            tuple(updated_flight if event.id == flight.id else event for event in itinerary.events)
        )
        disruption = FlightDisruption(
            flight_id=flight.id,
            old_departure=flight.start,
            new_departure=updated_flight.start,
            old_arrival=flight.end,
            new_arrival=updated_flight.end,
        )
        return updated, disruption