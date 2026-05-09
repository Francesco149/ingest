# llm_openai

## Purpose
Shared OpenAI-compatible chat client for local reasoning and vision LLM calls.

## Exports
```python
async def chat(
    prompt: str | list[dict[str, Any]],
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    config: dict | None = None,
) -> str
```

## Imports From
None.

## Behavior Rules
- Defaults `base_url`, `temperature`, `max_tokens`, and `timeout` from
  `config["api"]` when not passed explicitly.
- Sends requests to `{base_url}/v1/chat/completions`.
- Retries up to 10 attempts on transport errors, HTTP errors, and empty-content
  responses, adding increasingly direct nudges for repeat empty responses.
- Raises the final exception after the last attempt.

## Must NOT
- Import from task modules or engine
- Own task prompts; durable prompt text belongs in config
