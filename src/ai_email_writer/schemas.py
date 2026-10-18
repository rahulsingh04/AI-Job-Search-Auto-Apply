from typing import Optional
from pydantic import BaseModel, Field


class EmailResponse(BaseModel):
    """Structured output containing email body and optional dynamic subject."""

    subject: Optional[str] = Field(
        default=None,
        description="Personalized, respectful subject line tailored to recipient context."
    )
    body: str = Field(
        description="Complete professional email body with proper paragraphs and formatting."
    )
