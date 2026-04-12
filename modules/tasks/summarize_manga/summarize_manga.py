import logging
from typing import Dict, Any
from modules.task_manager.task_manager import Task
from modules.llm_openai import chat

log = logging.getLogger('task_summarize_manga')
POOL = "vision"

async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: summarize_manga
    Pool: rag
    Purpose: Generate a semantic search-optimized summary of manga gallery content.
    Input:
        url_slug        str (mandatory)
        metadata        dict  gallery metadata (title, tags)
        dep_*           dict  task outputs containing 'descriptions' list
    Output:
        reasoning_text  str
        url_slug        str (mandatory)
        descriptions    list of dicts
    """
    url_slug = input_data["url_slug"]
    log.info(f"Starting summarize_manga for slug: {url_slug}")
    
    metadata = input_data.get('metadata', {})
    
    # Extract title and tags for prompt
    title_obj = metadata.get('title', {})
    titles_str = (
        title_obj.get('japanese') or 
        title_obj.get('pretty') or 
        title_obj.get('english') or 
        'Unknown'
    )
    tags_str = ', '.join([t.get('name', '') for t in metadata.get('tags', [])])

    # Extract descriptions
    description_dicts = []
    for k, v in input_data.items():
        if k.startswith('dep_') and isinstance(v, dict) and 'descriptions' in v:
            for d in v['descriptions']:
                description_dicts.append({
                    'description': d['description'],
                    'start_page': d.get('start_page'),
                    'end_page': d.get('end_page'),
                    'url': d.get('url'),
                    'url_slug': d.get('url_slug')
                })
    description_dicts.sort(key=lambda x: x.get('start_page', 0))

    # Construct content body for prompt
    body_parts = []
    for d in description_dicts:
        line = f"## Page {d['start_page']}-{d['end_page']}\n{d['description']}"
        body_parts.append(line)
    content_body = '\n\n'.join(body_parts)

    log.info(
        f'{len(description_dicts)} descriptions | '
        f'content_body {len(content_body)} chars: {content_body[:50]} ...'
    )

    # Reasoning Prompt
    user_msg = (
        f'# {titles_str}\n'
        f'tags: {tags_str}\n'
        f'{content_body}\n\n'
        '# IMPORTANT INSTRUCTIONS\n'
        f'{context["config"]["prompts"]["manga_summarize"]["instructions"]}'
    )

    system_msg = context["config"]["prompts"]["manga_summarize"]["system"]
    response_text = await chat(
        prompt=user_msg,
        system_prompt=system_msg,
        config=context['config']
    )
    log.info(f'Response: {response_text[:50]}')

    if not response_text:
        log.error('No response text generated from LLM.')
        raise RuntimeError('No response text generated from LLM.')

    return {
        'reasoning_text': response_text,
        'start_page': description_dicts[0]['start_page'] if description_dicts else 0,
        'url_slug': url_slug,
        'descriptions': description_dicts
    }