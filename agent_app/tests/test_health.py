from pathlib import Path
import tomllib

from fastapi.testclient import TestClient

from deal_agent.config import Settings
from deal_agent.main import app

AGENT_APP_ROOT = Path(__file__).resolve().parents[1]


def test_health_endpoint_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_project_declares_build_backend_for_src_package():
    pyproject = tomllib.loads((AGENT_APP_ROOT / "pyproject.toml").read_text())

    assert pyproject["build-system"]["build-backend"] == "hatchling.build"
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/deal_agent"
    ]


def test_settings_env_file_is_project_root_relative():
    env_file = Path(Settings.model_config["env_file"])

    assert env_file.is_absolute()
    assert env_file == AGENT_APP_ROOT / ".env"
