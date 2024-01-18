from pydantic import BaseModel, Field


class GenericResponse(BaseModel):
    error: bool = Field(default=False, description='Self explanatory')
    message: str = Field(default="", description='Response message', examples=["OK", "error message"])