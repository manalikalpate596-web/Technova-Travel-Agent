from .models import WorkflowResult


def format_result(result: WorkflowResult) -> str:
    if result.fallback_reason:
        fallback = [f"LLM unavailable; deterministic fallback used: {result.fallback_reason}", ""]
    else:
        fallback = []
    lines = [
        *fallback,
        "TRAVEL DISRUPTION REPORT",
        "",
        "Original event:",
        _event_line(result.original_itinerary.event(result.disruption.flight_id)),
        "",
        "Disruption:",
        (
            f"{result.disruption.description}; arrival changed from "
            f"{result.disruption.old_arrival:%Y-%m-%d %H:%M} to "
            f"{result.disruption.new_arrival:%Y-%m-%d %H:%M}."
        ),
        "",
        "Affected dependencies:",
    ]
    if result.affected:
        lines.extend(
            f"- {result.original_itinerary.event(impact.event_id).title}: {impact.reason}."
            for impact in result.affected
        )
    else:
        lines.append("- None; dependent events remain feasible.")

    lines.extend(["", "Decisions:"])
    lines.extend(f"- {decision}" for decision in result.decisions)
    if result.agent_explanation:
        lines.extend(["", "Agent explanation:", result.agent_explanation])
    if result.needs_human_intervention:
        lines.append(f"- HUMAN INTERVENTION REQUIRED: {result.intervention_reason}")

    lines.extend(["", "Updated itinerary:"])
    for event in sorted(result.updated_itinerary.events, key=lambda item: item.start):
        reason = event.change_reason or "Unchanged; preserved from the original itinerary."
        lines.append(f"- {_event_line(event)} | Reason: {reason}")
    return "\n".join(lines)


def _event_line(event) -> str:
    return (
        f"{event.title} ({event.kind}) "
        f"{event.start:%Y-%m-%d %H:%M}-{event.end:%H:%M} at {event.location}"
    )