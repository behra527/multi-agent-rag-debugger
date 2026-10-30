
import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


def _extract_json(response: str) -> str:
    """Extract a JSON object from plain text or a Markdown code fence."""
    text = response.strip()

    if not text:
        return text

    # Remove a Markdown code fence when it wraps the entire response.
    if text.startswith("```"):
        lines = text.splitlines()

        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()

            if text.lower().startswith("json"):
                text = text[4:].lstrip()

    # Accept the response directly if it is valid JSON.
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Find the first complete JSON object while respecting strings
    # and escaped quotation marks.
    start = text.find("{")

    if start == -1:
        return text

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False

            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

            if depth == 0:
                return text[start:index + 1]

    # Return the original text so the caller can report a useful error.
    return text


def parse_json_response(response: str, model: type[T]) -> T:
    """Parse an LLM response and validate it against a Pydantic model."""
    if not response or not response.strip():
        raise ValueError("LLM returned an empty response.")

    json_text = _extract_json(response)

    try:
        data = json.loads(json_text)

    except json.JSONDecodeError as exc:
        # Limit diagnostic output to avoid exposing an entire model response.
        preview = json_text[:300].replace("\n", "\\n")

        raise ValueError(
            "LLM returned invalid JSON. "
            f"Reason: {exc.msg}. "
            f"Line: {exc.lineno}, "
            f"column: {exc.colno}. "
            f"Response length: {len(json_text)}. "
            f"Preview: {preview!r}"
        ) from exc

    try:
        return model.model_validate(data)

    except ValidationError as exc:
        # Report validation details without dumping the entire response.
        errors = exc.errors(
            include_input=False,
            include_url=False,
        )

        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'root'}: "
            f"{error['msg']}"
            for error in errors[:5]
        )

        raise ValueError(
            f"LLM response does not match {model.__name__}. "
            f"Validation errors: {details}"
        ) from exc
