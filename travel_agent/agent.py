from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol

from .models import DisruptionRequest, Itinerary, ReplanningOutcome, WorkflowResult
from .workflow import TravelReplanningWorkflow


class ChatCompletionClient(Protocol):
    def complete(
        self, *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "apply_flight_disruption",
            "description": "Apply the user's already-validated simulated flight change.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_dependencies",
            "description": "Analyze which dependent itinerary events no longer fit.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replan_itinerary",
            "description": "Run deterministic scheduling and conflict checks for affected events.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


class AgenticTravelPlanner:
    """Lets the model choose workflow tools; Python retains schedule authority."""

    def __init__(self, client: ChatCompletionClient, model: str, max_turns: int = 8) -> None:
        self.client = client
        self.model = model
        self.max_turns = max_turns

    def run(
        self,
        itinerary: Itinerary,
        request: DisruptionRequest,
        workflow: TravelReplanningWorkflow,
    ) -> WorkflowResult:
        request_text = _describe_request(request)
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are the planner for a travel-disruption workflow. Choose and call "
                    "exactly one tool per turn. First call apply_flight_disruption, then "
                    "read its result and call analyze_dependencies. If the analysis reports "
                    "affected events, call replan_itinerary; if none are affected, do not "
                    "replan and finish with the no-change decision. Read each tool result "
                    "before choosing the next step. These tools perform all schedule and "
                    "conflict calculations; never invent or alter event times. After the "
                    "needed tools return, provide a concise explanation grounded only in "
                    "their results. Do not request tool arguments; the validated user "
                    "request is supplied by the application."
                ),
            },
            {
                "role": "user",
                "content": f"{request_text}\nCurrent itinerary:\n{_itinerary_summary(itinerary)}",
            },
        ]

        disrupted = None
        disruption = None
        impacts = None
        outcome = None
        called_tools: list[str] = []

        for _ in range(self.max_turns):
            message = self.client.complete(
                model=self.model, messages=messages, tools=TOOL_SPECS
            )
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                if disrupted is None or disruption is None or impacts is None:
                    raise RuntimeError("Model finished before completing all required workflow tools")
                if outcome is None:
                    if impacts:
                        raise RuntimeError("Model finished before replanning affected events")
                    outcome = ReplanningOutcome(
                        itinerary=disrupted,
                        decisions=("No dependent event lost its feasible time slot; itinerary retained.",),
                    )
                return WorkflowResult(
                    original_itinerary=itinerary,
                    updated_itinerary=outcome.itinerary,
                    disruption=disruption,
                    affected=impacts,
                    decisions=outcome.decisions,
                    tool_calls=tuple(called_tools),
                    needs_human_intervention=outcome.needs_human_intervention,
                    intervention_reason=outcome.intervention_reason,
                    agent_explanation=(message.get("content") or "").strip(),
                )

            if len(tool_calls) != 1:
                raise RuntimeError("Planner must request one workflow tool at a time")

            call = tool_calls[0]
            function = call.get("function", {})
            name = function.get("name", "")
            arguments = function.get("arguments", "{}")
            if isinstance(arguments, str):
                arguments = json.loads(arguments or "{}")
            if arguments:
                tool_result: dict[str, Any] = {"error": "This workflow tool accepts no arguments."}
            else:
                try:
                    if name == "apply_flight_disruption" and disrupted is None:
                        disrupted, disruption = workflow.disruption_tool.apply(itinerary, request)
                        tool_result = {
                            "flight_id": disruption.flight_id,
                            "old_departure": _iso(disruption.old_departure),
                            "new_departure": _iso(disruption.new_departure),
                            "old_arrival": _iso(disruption.old_arrival),
                            "new_arrival": _iso(disruption.new_arrival),
                        }
                    elif name == "analyze_dependencies" and disrupted is not None and impacts is None:
                        impacts = workflow.dependency_agent.analyze(
                            itinerary,
                            disrupted,
                            disruption,
                            workflow.replanning_agent.transfer_buffer,
                        )
                        tool_result = {
                            "affected": [
                                {
                                    "event_id": impact.event_id,
                                    "reason": impact.reason,
                                    "required_after": _iso(impact.required_after),
                                }
                                for impact in impacts
                            ]
                        }
                    elif name == "replan_itinerary" and disrupted is not None and impacts is not None and outcome is None:
                        outcome = workflow.replanning_agent.replan(
                            itinerary, disrupted, disruption, impacts
                        )
                        tool_result = {
                            "decisions": list(outcome.decisions),
                            "needs_human_intervention": outcome.needs_human_intervention,
                            "intervention_reason": outcome.intervention_reason,
                            "updated_itinerary": [
                                {
                                    "id": event.id,
                                    "title": event.title,
                                    "start": _iso(event.start),
                                    "end": _iso(event.end),
                                    "change_reason": event.change_reason,
                                }
                                for event in outcome.itinerary.events
                            ],
                        }
                    else:
                        tool_result = {
                            "error": f"Tool {name!r} is unknown, premature, or already completed."
                        }
                except Exception as error:
                    tool_result = {"error": f"{type(error).__name__}: {error}"}

            if "error" not in tool_result:
                called_tools.append(name)
            messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "content": json.dumps(tool_result),
                }
            )

        raise RuntimeError(f"Planner exceeded the {self.max_turns}-turn tool limit")


def _describe_request(request: DisruptionRequest) -> str:
    if request.delay_by_seconds is not None:
        hours = request.delay_by_seconds / 3600
        return f"User request: delay flight {request.flight_id} by {hours:g} hours."
    return (
        f"User request: change flight {request.flight_id} departure to "
        f"{request.new_departure:%Y-%m-%d %H:%M}."
    )


def _itinerary_summary(itinerary: Itinerary) -> str:
    return "\n".join(
        f"{event.id} [{event.kind}] {event.title}: "
        f"{_iso(event.start)} to {_iso(event.end)}; depends on {event.dependencies or 'none'}"
        for event in itinerary.events
    )


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="minutes")