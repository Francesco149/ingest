import logging
import asyncio
import math
from typing import Any, Dict, List

log = logging.getLogger("modules.tasks.chunk_article.chunk_article")

def chunk_text(text: str, chunk_size: int = 10000) -> List[str]:
    """
    Splits text into balanced chunks of roughly chunk_size length,
    avoiding splitting in the middle of words where possible.
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        if end < text_len:
            # Look for a space or newline to avoid cutting words
            last_space = text.rfind(' ', start, end + 1)
            last_newline = text.rfind('\n', start, end + 1)
            
            # Prefer splitting at newline if available, otherwise at space
            split_pos = max(last_space, last_newline)
            
            if split_pos != -1 and split_pos > start:
                end = split_pos
            else:
                # If no whitespace found, just hard cut
                pass
        
        chunks.append(text[start:end].strip())
        start = end
        
        # Skip any whitespace between chunks
        while start < text_len and text[start].isspace():
            start += 1

    return [c for c in chunks if c]

async def run(task: Any, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    The Fan-out: Chunks the text and creates sub-tasks.
    """
    full_text = input_data.get("content", "")
    if not full_text:
        return {"chunks": []}

    log.info(f"Chunking article content of length {len(full_text)}")
    
    chunks = chunk_text(full_text)
    num_chunks = len(chunks)
    log.info(f"Created {num_chunks} chunks.")

    # We need to create a task for each chunk.
    task_ids = []
    for i, chunk in enumerate(chunks):
        task_id = await context['task_manager'].create_task(
            "summarize_text_chunk",
            input_data={"text": chunk, "chunk_index": i}
        )
        task_ids.append(task_id)

    # Now, we create the 'summarize_article' task (the reducer)
    # We pass the metadata through so the reducer can pass it to index_article.
    metadata_payload = {
        "url": input_data.get("url"),
        "url_slug": input_data.get("url_slug"),
        "title": input_data.get("title"),
        "content": full_text
    }

    await context['task_manager'].create_task(
        "summarize_article",
        input_data=metadata_payload,
        dependencies=task_ids
    )

    log.info(f"Fanned out {num_chunks} chunk tasks and scheduled the reducer task.")
    
    return {"chunk_count": num_chunks, "task_ids": task_ids}