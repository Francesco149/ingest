"""
Task: download_manga
Pool: download_pool
Input:
    gallery_id    str  manga gallery ID
    download_dir  str  directory to save images
    note          str  optional user note
    url           str  url (for logging)
    url_slug      str (mandatory)
Output:
    gallery_id    str  echoed gallery ID
    image_paths   list[str] paths to downloaded images
    metadata      dict  gallery metadata
    desc_task_ids list[str] IDs of all created describe_manga_page tasks
    transcribe_task_ids list[str] IDs of all created transcribe_manga tasks
    url_slug      str (mandatory)
    image_info    list[dict] list of image information (path, url, etc.)
Creates:
    describe_manga_page  — one per image (includes metadata); dep: this task
    summarize_manga  — summarizes the page; dep: describe_manga_page
    transcribe_manga  — transcribes the summary; dep: summarize_manga
    index_manga  — indexes the gallery; dep: all transcribe_manga tasks
"""

import logging
import math
from pathlib import Path
from typing import Dict, Any

from modules.task_manager.task_manager import Task
from modules.fetcher_manga.fetcher_manga import fetch_gallery

log = logging.getLogger('task_download_manga')
POOL = "download"

async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    def sliding_window_iterator(items, size, overlap):
        if not items:
            return
        step = size - overlap
        for i in range(0, len(items), step):
            chunk = items[i : i + size]
            yield chunk, i
            # If we've reached or passed the end, stop
            if i + size >= len(items):
                break

    url_slug = input_data["url_slug"]
    gallery_id = input_data["gallery_id"]
    url = input_data.get("url")
    metadata = input_data.get("metadata", {})
    target_path = Path(input_data['download_dir']) / url_slug
    download_dir = target_path
    note = input_data.get('note', '')

    log.info(f"Starting download_manga for slug: {url_slug}")

    task_manager = context['task_manager']
    
    result = await fetch_gallery(gallery_id, download_dir, context['config'])
    image_info = result['image_info']
    metadata = result['metadata']
    log.info(f'Successfully downloaded {len(image_info)} images for gallery {gallery_id}')

    # Fan out describe_manga_page tasks
    all_image_paths = [info['path'] for info in image_info]
    
    desc_task_ids = []
    transcribe_task_ids = []
    manga_cfg = context['config']['manga']
    batch_size = manga_cfg['description_batch_size']
    overlap = manga_cfg['description_overlap']

    for chunk, start_idx in sliding_window_iterator(all_image_paths, batch_size, overlap):
        desc_id = await task_manager.create_task(
            'describe_manga_page',
            {
                'image_paths': chunk,
                'url': url,
                'url_slug': url_slug,
                'gallery_id': gallery_id,
                'metadata': metadata,
                'start_page': start_idx + 1,
                'end_page': start_idx + len(chunk)
            },
            dependencies=[task.id],
        )
        desc_task_ids.append(desc_id)
            
    manga_cfg = context['config']['manga']
    summary_max_batch_size = manga_cfg['summary_max_batch_size']
    
    if desc_task_ids:
        num_batches = math.ceil(len(desc_task_ids) / summary_max_batch_size)
        batch_size_per_batch = len(desc_task_ids) // num_batches
        remainder = len(desc_task_ids) % num_batches
        
        current_idx = 0
        for i in range(num_batches):
            size = batch_size_per_batch + (1 if i < remainder else 0)
            batch_ids = desc_task_ids[current_idx : current_idx + size]
            current_idx += size
            
            summarize_id = await task_manager.create_task(
                'summarize_manga',
                {
                    'url': url,
                    'url_slug': url_slug,
                    'gallery_id': gallery_id,
                    'metadata': metadata
                },
                dependencies=batch_ids
            )
            
            transcribe_id = await task_manager.create_task(
                'transcribe_manga',
                {
                    'url': url,
                    'url_slug': url_slug,
                    'gallery_id': gallery_id,
                    'metadata': metadata
                },
                dependencies=[summarize_id]
            )
            transcribe_task_ids.append(transcribe_id)

    image_paths = all_image_paths

    await task_manager.create_task(
        'index_manga',
        {
            'gallery_id': gallery_id,
            'metadata': metadata,
            'url_slug': url_slug,
            'url': url,
            'retriable': 1
        },
        dependencies=transcribe_task_ids
    )

    return {
        'gallery_id': gallery_id,
        'image_paths': image_paths,
        'metadata': metadata,
        'desc_task_ids': desc_task_ids,
        'transcribe_task_ids': transcribe_task_ids,
        'url_slug': url_slug,
        'image_info': image_info
    }
