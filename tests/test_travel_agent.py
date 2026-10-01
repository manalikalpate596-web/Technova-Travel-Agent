from dataclasses import replace
from datetime import datetime, timedelta
import unittest

from travel_agent.agent import AgenticTravelPlanner
from travel_agent import DisruptionRequest, TravelReplanningWorkflow, default_itinerary
from travel_agent.communication import format_result


class FakeModelClient:
    def __init__(self, messages: list[dict]) -> None:
        self.responses = list(messages)
        self.requests = []

    def complete(self, *, model: str, messages: list[dict], tools: list[dict]) -> dict:
        self.requests.append({"model": model, "messages": messages, "tools": tools})
        return self.responses.pop(0)


class TravelReplanningWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = TravelReplanningWorkflow()

    def test_delay_moves_dependent_meeting(self) -> None:
        original = default_itinerary()
        result = self.workflow.run(
            original,
            DisruptionRequest(flight_id="flight-1", delay_by_seconds=4 * 60 * 60),
        )

        self.assertIn("meeting-1", {impact.event_id for impact in result.affected})
        self.assertGreater(
            result.updated_itinerary.event("meeting-1").start,
            original.event("meeting-1").start,
        )
        self.assertFalse(result.needs_human_intervention)
        self.assertIn("ReplanningAgent.replan", result.tool_calls)

    def test_unrelated_activity_is_not_affected_or_moved(self) -> None:
        original = default_itinerary()
        result = self.workflow.run(
            original,
            DisruptionRequest(flight_id="flight-1", delay_by_seconds=4 * 60 * 60),
        )

        self.assertNotIn("activity-1", {impact.event_id for impact in result.affected})
        self.assertEqual(
            result.updated_itinerary.event("activity-1"), original.event("activity-1")
        )

    def test_non_movable_affected_meeting_requests_human_intervention(self) -> None:
        original = default_itinerary()
        events = tuple(
            replace(event, movable=False) if event.id == "meeting-1" else event
            for event in original.events
        )
        original = original.with_events(events)
        result = self.workflow.run(
            original,
            DisruptionRequest(flight_id="flight-1", delay_by_seconds=4 * 60 * 60),
        )

        self.assertTrue(result.needs_human_intervention)
        self.assertIn("non-movable", result.intervention_reason)
        self.assertEqual(
            result.updated_itinerary.event("meeting-1"), original.event("meeting-1")
        )

    def test_meeting_outside_allowed_window_requests_human_intervention(self) -> None:
        original = default_itinerary()
        events = tuple(
            replace(event, latest_start=datetime(2026, 10, 20, 18, 30))
            if event.id == "meeting-1"
            else event
            for event in original.events
        )
        original = original.with_events(events)

        result = self.workflow.run(
            original,
            DisruptionRequest(flight_id="flight-1", delay_by_seconds=6 * 60 * 60),
        )

        self.assertTrue(result.needs_human_intervention)
        self.assertIn("No conflict-free slot", result.intervention_reason)
        self.assertIn("meeting-1", {impact.event_id for impact in result.affected})
        self.assertEqual(
            result.updated_itinerary.event("meeting-1"), original.event("meeting-1")
        )
        self.assertEqual(
            result.updated_itinerary.event("hotel-1"), original.event("hotel-1")
        )
        self.assertNotEqual(
            result.updated_itinerary.event("flight-1"), original.event("flight-1")
        )

    def test_small_delay_leaves_all_downstream_events_feasible(self) -> None:
        result = self.workflow.run(
            default_itinerary(),
            DisruptionRequest(flight_id="flight-1", delay_by_seconds=60 * 60),
        )

        self.assertEqual(result.affected, ())
        self.assertIn("No dependent event", result.decisions[0])

    def test_report_explains_disruption_and_event_changes(self) -> None:
        result = self.workflow.run(
            default_itinerary(),
            DisruptionRequest(flight_id="flight-1", delay_by_seconds=4 * 60 * 60),
        )

        report = format_result(result)
        self.assertIn("Original event:", report)
        self.assertIn("Disruption:", report)
        self.assertIn("Affected dependencies:", report)
        self.assertIn("Reason:", report)
        self.assertIn("Simulated disruption changed departure", report)

    def test_model_layer_calls_tools_and_uses_results_before_next_step(self) -> None:
        responses = [
            {"tool_calls": [{"id": "1", "function": {"name": "apply_flight_disruption", "arguments": "{}"}}]},
            {"tool_calls": [{"id": "2", "function": {"name": "analyze_dependencies", "arguments": "{}"}}]},
            {"tool_calls": [{"id": "3", "function": {"name": "replan_itinerary", "arguments": "{}"}}]},
            {"content": "I moved the dependent hotel and meeting while preserving the museum visit."},
        ]
        fake = FakeModelClient(responses)
        original = default_itinerary()
        result = AgenticTravelPlanner(fake, model="fake-model").run(
            original,
            DisruptionRequest(flight_id="flight-1", delay_by_seconds=4 * 60 * 60),
            self.workflow,
        )

        self.assertEqual(
            result.tool_calls,
            ("apply_flight_disruption", "analyze_dependencies", "replan_itinerary"),
        )
        self.assertEqual(len(fake.requests), 4)
        dependency_turn = fake.requests[2]["messages"]
        self.assertTrue(any(message.get("role") == "tool" for message in dependency_turn))
        replanning_turn = fake.requests[3]["messages"]
        self.assertTrue(any(message.get("role") == "tool" for message in replanning_turn))
        self.assertEqual(
            result.agent_explanation,
            "I moved the dependent hotel and meeting while preserving the museum visit.",
        )

    def test_model_skips_replanning_when_analysis_finds_no_affected_events(self) -> None:
        fake = FakeModelClient(
            [
                {"tool_calls": [{"id": "1", "function": {"name": "apply_flight_disruption", "arguments": "{}"}}]},
                {"tool_calls": [{"id": "2", "function": {"name": "analyze_dependencies", "arguments": "{}"}}]},
                {"content": "The one-hour delay leaves all dependent events feasible, so no replan is needed."},
            ]
        )
        original = default_itinerary()
        result = AgenticTravelPlanner(fake, model="fake-model").run(
            original,
            DisruptionRequest(flight_id="flight-1", delay_by_seconds=60 * 60),
            self.workflow,
        )

        self.assertEqual(
            result.tool_calls, ("apply_flight_disruption", "analyze_dependencies")
        )
        self.assertEqual(result.affected, ())
        self.assertEqual(result.updated_itinerary.event("meeting-1"), original.event("meeting-1"))


if __name__ == "__main__":
    unittest.main()