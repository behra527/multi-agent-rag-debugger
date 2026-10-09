import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


def parse_json_response(response: str, model: type[T]) -> T:
    """Parse and validate a JSON LLM response against a Pydantic model."""

    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM returned invalid JSON.") from exc

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"LLM response does not match {model.__name__}."
        ) from exc