import logging
import asyncio
from typing import Any, Dict
from modules.task_manager.task_manager import Task
from modules.llm_openai import chat

log = logging.getLogger("modules.tasks.summarize_text_chunk.summarize_text_chunk")

async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Summarizes a single chunk of text using an LLM to maximize semantic searchability.
    """
    text = input_data.get("text", "")
    if not text:
        return {"summary": ""}

    log.info(f"Summarizing text chunk of length: {len(text)}")

    prompt = (
        "You are an expert analyst and Semantic Search Optimizer. "
        "Summarize the following text chunk, focusing on extracting key entities, "
        "themes, tropes, and narrative descriptions to maximize semantic searchability. "
        "Ensure the summary is concise but information-dense.\n\n"
        f"Text: {text}"
    )

    try:
        system_msg = "You are an expert analyst and Semantic Search Optimizer."
        summary_text = await chat(
            prompt=prompt,
            system_prompt=system_msg,
            model='local-model',
            temperature=0.7,
            config=context['config']
        )
        return {"summary": summary_text}
    except Exception as e:
        log.error(f"Summarization task failed: {e}")
        return {"summary": ""}