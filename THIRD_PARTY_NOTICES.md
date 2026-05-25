# Third Party Notices

This hackathon MVP integrates with external tools and APIs but does not vendor their source code.

## External Tools And APIs

- NVIDIA NemoClaw: referenced as the local sandbox, policy, and skill runtime for guarded agent execution.
- NVIDIA NIM Serverless Inference: referenced as the hosted model API used by the live model client.
- Odoo: used as the ERP/CRM demo surface through Docker and a custom addon mounted into `/mnt/extra-addons`.
- Linear API: used by the agent to create project and engineering work-tracking artifacts.
- GitHub API: used by the agent to create delivery issues and repository-facing traceability artifacts.
- Telegram Bot API: used by the agent to send stakeholder demo notifications.

## Python Dependencies

- FastAPI: local API server framework for the agent app.
- httpx: HTTP client used by live connectors and NIM calls.
- Pydantic: domain model validation and serialization.
- pytest: local test runner for the MVP smoke, unit, and workflow tests.

Refer to each upstream project or service for its current license and terms. Runtime credentials must be supplied locally and must not be committed to this repository.
