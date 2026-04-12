import logging
import httpx
import asyncio
from typing import Any, Dict, List, Optional, Union

log = logging.getLogger(__name__)

async def chat(
    prompt: Union[str, List[Dict[str, Any]]],
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    A unified helper for OpenAI-compatible chat completions.
    Includes retry logic for transient empty responses.
    """
    if config is None:
        config = {}

    api_cfg = config.get('api', {})
    if base_url is None:
        base_url = api_cfg.get('reasoning_llama_base')
    if model is None:
        model = 'local-model'
    if temperature is None:
        temperature = api_cfg.get('llama_temperature')
    if max_tokens is None:
        max_tokens = api_cfg.get('reasoning_max_tokens')
    if timeout is None:
        timeout = api_cfg.get('llama_timeout')
    if api_key is None:
        api_key = ""

    endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    payload_template = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    nudges = [
        "Please provide a non-empty response.",
        "Please provide a detailed response.",
        "The response was empty, please try again.",
        "Please provide a meaningful answer.",
        "Please don't be silent, provide a response.",
        "Please ensure you provide a response.",
        "Please provide a response.",
        "Please try again.",
        "Please respond with content.",
        "Please provide a response."
    ]

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(10):
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})

                if isinstance(prompt, str):
                    content_to_send = prompt
                    if attempt > 0:
                        content_to_send += f"\n\n[Nudge: {nudges[min(attempt-1, len(nudges)-1)]}]"
                    messages.append({"role": "user", "content": content_to_send})
                else:
                    messages.extend(prompt)
                    if attempt > 0:
                        messages.append({"role": "user", "content": nudges[min(attempt-1, len(nudges)-1)]})

                payload = {**payload_template, "messages": messages}
                payload = {k: v for k, v in payload.items() if v is not None}

                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]

                if not content or not content.strip():
                    raise ValueError("LLM returned an empty content string.")
                
                return content

            except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as e:
                if attempt == 9:
                    raise e
                log.warning(f"LLM attempt {attempt + 1} failed: {e}. Retrying...")
                await asyncio.sleep(1)
