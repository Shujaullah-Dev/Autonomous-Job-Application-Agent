
import uuid

from pydantic import BaseModel, Field


class ResumeUploadResponse(BaseModel):
    candidate_id: uuid.UUID
    filename: str
    file_type: str
    extracted_text: str
    character_count: int = Field(ge=0)
    message: str
