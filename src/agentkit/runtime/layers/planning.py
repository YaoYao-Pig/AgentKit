from __future__ import annotations

from dataclasses import dataclass, field

from ..interfaces import Planner
from ..models import Action, PipelineState, Task, TaskModel


@dataclass(slots=True)
class MinimalPlanner(Planner):
    default_action_type: str = "mock_action"
    default_action_params: dict[str, object] = field(default_factory=dict)

    def model_task(self, task: Task, state: PipelineState) -> TaskModel:
        state.current_phase = "planning"
        params = {"goal": task.goal, **self.default_action_params}
        action = Action(
            id=f"{task.id}-step-1",
            action_type=self.default_action_type,
            params=params,
        )
        return TaskModel(
            task=task,
            global_plan=["model_task", "execute_actions", "validate_task"],
            next_actions=[action],
            risk_points=[],
        )

    def replan(self, task: Task, state: PipelineState, reason: str) -> TaskModel:
        state.current_phase = "replan"
        params = {"goal": task.goal, "replan_reason": reason, **self.default_action_params}
        action = Action(
            id=f"{task.id}-replan-{len(state.records) + 1}",
            action_type=self.default_action_type,
            params=params,
        )
        return TaskModel(
            task=task,
            global_plan=["replan", "execute_actions", "validate_task"],
            next_actions=[action],
            risk_points=[reason],
        )
