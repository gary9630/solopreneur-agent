from fastapi import Depends, FastAPI
from pydantic import BaseModel, ConfigDict

from deal_agent.connectors import (
    FakeGitHubConnector,
    FakeLinearConnector,
    FakeOdooConnector,
    FakeTelegramConnector,
)
from deal_agent.models import WorkflowRun
from deal_agent.runner import DealWorkflowRunner, WorkflowRunFailed
from deal_agent.services import FakeModelServices

app = FastAPI(title="Deal Agent")


class DemoWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    message: str


def create_demo_runner() -> DealWorkflowRunner:
    return DealWorkflowRunner(
        models=FakeModelServices(),
        odoo=FakeOdooConnector(),
        linear=FakeLinearConnector(),
        github=FakeGitHubConnector(),
        telegram=FakeTelegramConnector(),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/workflows/demo", response_model=WorkflowRun)
def run_demo_workflow(
    request: DemoWorkflowRequest,
    runner: DealWorkflowRunner = Depends(create_demo_runner),
) -> WorkflowRun:
    try:
        return runner.run(request.run_id, request.message)
    except WorkflowRunFailed as exc:
        return exc.run
