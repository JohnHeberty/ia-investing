from pydantic import BaseModel, ConfigDict


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
