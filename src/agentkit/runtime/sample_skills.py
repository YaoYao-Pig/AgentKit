from __future__ import annotations

from typing import Any

from .models import PipelineState


def health_check(params: dict[str, Any], state: PipelineState) -> dict[str, Any]:
    return {
        "status": "success",
        "message": "python callable skill is healthy",
        "task_id": state.task_id,
        "received": params,
    }
