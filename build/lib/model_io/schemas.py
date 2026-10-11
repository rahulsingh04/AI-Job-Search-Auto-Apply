from pydantic import BaseModel, Field


class EmailResponse(BaseModel):
    """Structured output containing only the email body."""

    body: str = Field(
        description="Complete professional email body with proper paragraphs and formatting."
    )
