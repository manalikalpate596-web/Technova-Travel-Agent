import argparse
import os
from dataclasses import replace
from datetime import timedelta

from .agent import AgenticTravelPlanner
from .communication import format_result
from .data import default_itinerary
from .model_client import client_from_env
from .models import DisruptionRequest
from .workflow import TravelReplanningWorkflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the simulated travel replanning demo.")
    parser.add_argument(
        "--delay-hours", type=float, default=4.0, help="Simulated flight delay in hours"
    )
    args = parser.parse_args()
    if args.delay_hours < 0:
        parser.error("--delay-hours must be non-negative")

    itinerary = default_itinerary()
    request = DisruptionRequest(
        flight_id="flight-1",
        delay_by_seconds=int(timedelta(hours=args.delay_hours).total_seconds()),
    )
    workflow = TravelReplanningWorkflow()
    client, unavailable_reason = client_from_env()
    if client is None:
        result = replace(
            workflow.run(itinerary, request), fallback_reason=unavailable_reason
        )
    else:
        try:
            result = AgenticTravelPlanner(client, model=os.environ["AGENT_MODEL"]).run(
                itinerary, request, workflow
            )
        except Exception as error:
            fallback_reason = (
                f"{type(error).__name__}: {error}; deterministic workflow used."
            )
            result = replace(
                workflow.run(itinerary, request), fallback_reason=fallback_reason
            )
    print(format_result(result))


if __name__ == "__main__":
    main()