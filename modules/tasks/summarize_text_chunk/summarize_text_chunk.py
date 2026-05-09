"""
Task: summarize_text_chunk
Pool: vision
Input:
    text         str  text chunk to summarize
    chunk_index  int  source chunk index
Output:
    summary      str  semantic-search-oriented chunk summary
Creates: nothing
"""

import logging
from typing import Any, Dict
from modules.task_manager.task_manager import Task
from modules.llm_openai import chat

log = logging.getLogger("modules.tasks.summarize_text_chunk.summarize_text_chunk")
POOL = "vision"

async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Summarizes a single chunk of text using an LLM to maximize semantic searchability.
    """
    text = input_data.get("text", "")
    if not text:
        return {"summary": ""}

    log.info(f"Summarizing text chunk of length: {len(text)}")

    prompt_cfg = context['config']['prompts']['text_chunk_summary']
    prompt = prompt_cfg['user_template'].format(text=text)

    try:
        summary_text = await chat(
            prompt=prompt,
            system_prompt=prompt_cfg['system'],
            model='local-model',
            temperature=0.7,
            config=context['config']
        )
        return {"summary": summary_text}
    except Exception as e:
        log.error(f"Summarization task failed: {e}")
        raise
