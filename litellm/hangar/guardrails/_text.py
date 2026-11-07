"""Helpers to pull user-visible text out of OpenAI-style request / response objects."""

from collections.abc import Iterator, Mapping


def _content_text(content: object) -> Iterator[str]:
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, Mapping):
                text = part.get("text")
                if isinstance(text, str):
                    yield text
            elif isinstance(part, str):
                yield part


def request_texts(data: Mapping[str, object]) -> list[str]:
    texts: list[str] = []  # mutable-ok: collected text segments
    messages = data.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, Mapping):
                texts.extend(_content_text(message.get("content")))
    for field in ("prompt", "input"):
        value = data.get(field)
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, list):
            texts.extend(v for v in value if isinstance(v, str))
            for v in value:
                if isinstance(v, Mapping):
                    texts.extend(_content_text(v.get("content")))
    return texts


def last_user_text(data: Mapping[str, object]) -> str:
    messages = data.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, Mapping) and message.get("role") == "user":
                return "\n".join(_content_text(message.get("content")))
    return "\n".join(request_texts(data))


def response_texts(response: object) -> list[str]:
    texts: list[str] = []  # mutable-ok: collected text segments
    choices = getattr(response, "choices", None)
    if isinstance(choices, list):
        for choice in choices:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str):
                texts.append(content)
            text = getattr(choice, "text", None)
            if isinstance(text, str):
                texts.append(text)
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        texts.append(output_text)
    return texts


def load_list_setting(value: object) -> list[str]:
    """A module setting that is either a list or a path to a newline-separated file."""
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str):
        try:
            with open(value, encoding="utf-8") as handle:
                return [line.strip() for line in handle if line.strip()]
        except OSError as e:
            raise ValueError(f"Could not read list file {value!r}: {e}") from e
    return []
