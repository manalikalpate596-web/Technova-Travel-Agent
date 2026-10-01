from datetime import timedelta

from .dependency_agent import DependencyAnalysisAgent
from .models import DisruptionRequest, WorkflowResult
from .replanning_agent import ReplanningAgent
from .tools import SimulatedFlightDisruptionTool


class TravelReplanningWorkflow:
    """Coordinates simulated tool use, dependency analysis, and replanning."""

    def __init__(self, transfer_buffer: timedelta = timedelta(minutes=45)) -> None:
        self.disruption_tool = SimulatedFlightDisruptionTool()
        self.dependency_agent = DependencyAnalysisAgent()
        self.replanning_agent = ReplanningAgent(transfer_buffer=transfer_buffer)

    def run(self, itinerary, request: DisruptionRequest) -> WorkflowResult:
        disrupted, disruption = self.disruption_tool.apply(itinerary, request)
        impacts = self.dependency_agent.analyze(
            itinerary, disrupted, disruption, self.replanning_agent.transfer_buffer
        )
        outcome = self.replanning_agent.replan(
            itinerary, disrupted, disruption, impacts
        )
        return WorkflowResult(
            original_itinerary=itinerary,
            updated_itinerary=outcome.itinerary,
            disruption=disruption,
            affected=impacts,
            decisions=outcome.decisions,
            tool_calls=(
                "SimulatedFlightDisruptionTool.apply",
                "DependencyAnalysisAgent.analyze",
                "ReplanningAgent.replan",
            ),
            needs_human_intervention=outcome.needs_human_intervention,
            intervention_reason=outcome.intervention_reason,
        )