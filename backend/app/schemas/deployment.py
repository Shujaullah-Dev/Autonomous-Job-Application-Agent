"""Safe deployment diagnostics returned to developers."""

from typing import Literal

from pydantic import BaseModel


class DeploymentStatusResponse(BaseModel):
    app_name: str
    app_env: str
    containerized: bool

    database_backend: str

    workflow_checkpoint: Literal["process_memory"]
    notification_processing: Literal["one_shot"]
    schema_migrations: Literal["manual"]

    automatic_submission_enabled: bool

    message: str