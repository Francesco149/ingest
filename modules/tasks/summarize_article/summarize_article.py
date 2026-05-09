"""
Task: summarize_article
Pool: vision
Input:
    url       str  original article URL
    url_slug  str  url slug (mandatory)
    title     str  article title
    content   str  full article Markdown
Input (via dep_ enrichment from summarize_text_chunk):
    summary   str  chunk summary text
Output:
    url_slug  str  url slug (mandatory)
    summary   str  final article summary
Creates:
    index_article  — one task with article content and final summary
"""

import logging
import re
from typing import Any, Dict
from modules.task_manager.task_manager import Task
from modules.llm_openai import chat

logger = logging.getLogger(__name__)
POOL = "vision"

async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Implementation of the summarize_article task.
    """
    try:
        logger.info("Starting summarize_article task.")

        # 1. Collect all summaries from keys starting with 'dep_'
        summaries = []
        for key, value in input_data.items():
            if key.startswith("dep_") and isinstance(value, dict):
                summary_text = value.get("summary")
                if summary_text:
                    summaries.append(str(summary_text))

        # 2-4. Determine final_summary based on count
        if not summaries:
            final_summary = ""
        elif len(summaries) == 1:
            final_summary = summaries[0]
        else:
            logger.info(f"Multiple summaries ({len(summaries)}) found. Consolidating via LLM.")
            combined_text = "\n".join(summaries)
            prompt_cfg = context['config']['prompts']['article_summary']
            prompt = prompt_cfg['user_template'].format(combined_text=combined_text)
            final_summary = await chat(
                prompt=prompt,
                system_prompt=prompt_cfg['system'],
                temperature=0.3,
                config=context['config']
            )

        # 7. Prepare input for index_article
        title = input_data.get('title', 'untitled')
        url_slug = input_data.get('url_slug', '')
        url = input_data.get('url', '')
        content = input_data.get('content', '')

        # Derived filename: title_slug-url_slug.md
        # Create a slug from title (lowercase, alphanumeric/underscores)
        title_slug = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
        filename = f"{title_slug}-{url_slug}.md"

        index_input = {
            "url_slug": url_slug,
            "url": url,
            "filename": filename,
            "content": content,
            "title": title,
            "summary": final_summary
        }

        # 6. Trigger the index_article task
        logger.info(f"Triggering index_article task for slug: {url_slug}")
        await context['task_manager'].create_task('index_article', input_data=index_input)

        logger.info("summarize_article task completed successfully.")
        
        return {
            "url_slug": url_slug,
            "summary": final_summary
        }

    except Exception as e:
        logger.error(f"Error during summarize_article task: {str(e)}", exc_info=True)
        raise
