from pydantic import BaseModel, ConfigDict, Field, field_validator


class EdgeCreate(BaseModel):
    source: str
    destination: str
    latency: float = Field(gt=0, allow_inf_nan=False)

    @field_validator("source", "destination")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class EdgeResponse(BaseModel):
    id: int
    source: str
    destination: str
    latency: float

    model_config = ConfigDict(from_attributes=True)
