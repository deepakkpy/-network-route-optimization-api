from pydantic import BaseModel, ConfigDict, field_validator


class NodeCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class NodeResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
