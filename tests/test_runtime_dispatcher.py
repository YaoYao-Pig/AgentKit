from agentkit.config.models import SkillConfig, SkillsIndexConfig
from agentkit.runtime.dispatcher import SkillDispatcherExecutor
from agentkit.runtime.models import Action, PipelineState, TaskStatus


def test_dispatcher_executes_python_callable_skill() -> None:
    skills = SkillsIndexConfig(
        skills={
            "python_health_check": SkillConfig(
                purpose="health",
                adapter="python_callable",
                module="agentkit.runtime.sample_skills",
                function="health_check",
            )
        }
    )
    executor = SkillDispatcherExecutor.from_skills_index(skills)

    state = PipelineState(task_id="dispatch-1", status=TaskStatus.EXECUTING)
    action = Action(id="a1", action_type="python_health_check", params={"x": 1})
    result = executor.execute(action, state)

    assert result.status == "success"
    assert result.output["adapter"] == "python_callable"
    assert result.output["received"]["x"] == 1


def test_dispatcher_handles_unknown_action_type() -> None:
    skills = SkillsIndexConfig(skills={})
    executor = SkillDispatcherExecutor.from_skills_index(skills)
    state = PipelineState(task_id="dispatch-2")
    action = Action(id="a2", action_type="missing_skill", params={})

    result = executor.execute(action, state)

    assert result.status == "failed"
    assert result.output["error"] == "unknown_action_type"
