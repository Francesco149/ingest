import logging
import httpx
import asyncio
from pathlib import Path
from modules.task_manager.task_manager import RateLimitError

log = logging.getLogger('modules.fetcher_manga.fetcher_manga')

async def fetch_gallery(gallery_id: str, download_dir: str, config: dict) -> dict:
    """
    Fetches gallery metadata and downloads all images.
    """
    api_url = f"{config['api']['manga_api_url'].rstrip('/')}/galleries/{gallery_id}/"
    download_path = Path(download_dir)
    download_path.mkdir(parents=True, exist_ok=True)

    api_key = config['api']['manga_api_key']

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        log.info(f'Fetching metadata for gallery {gallery_id}')
        headers = {'Authorization': f'Key {api_key}'} if api_key else {}
        resp = await client.get(api_url, headers=headers)
        resp.raise_for_status()
        metadata = resp.json()
        log.debug(f'Metadata keys: {list(metadata.keys())}')

        # In a real manga API scenario, the image URLs would be in the metadata
        # For this implementation, we assume the API provides a 'pages' list of objects
        pages = metadata.get('pages', [])
        
        if not pages:
            log.warning(f'No pages found for gallery {gallery_id}')
            return {'metadata': metadata, 'image_info': []}

        image_info = []
        tasks = []
        task_to_info_map = []
        servers = metadata.get('image_servers', ['i3.manga.net'])
        
        async def _download_task(u, p):
            log.info(f'Downloading {u}')
            try:
                img_resp = await client.get(u, headers=headers)
                img_resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    raise RateLimitError()
                raise
            
            p.write_bytes(img_resp.content)
            return str(p)

        for i, page in enumerate(pages):
            url_path = page.get('path')
            if not url_path:
                log.warning(f"Page {i} missing 'path' key. Page content: {page}")
                continue
            
            server = servers[i % len(servers)]
            url = f"https://{server}/{url_path}"
            file_path = download_path / f'image_{i:03d}.jpg'

            image_info.append({'path': str(file_path), 'url': url})

            if file_path.exists():
                log.info(f"File already exists: {file_path}, skipping download.")
                continue

            task = asyncio.create_task(_download_task(url, file_path))
            task.set_name(f"dl_img:{i:03d}")
            tasks.append(task)
            task_to_info_map.append(len(image_info) - 1)

        # Keep page downloads inside this task's download worker. Do not submit
        # nested jobs to worker pools; the task manager owns pool scheduling.
        if tasks:
            downloaded_paths = await asyncio.gather(*tasks)
            
            # Update the paths in image_info with the actual returned paths from the tasks
            for idx, path in enumerate(downloaded_paths):
                info_idx = task_to_info_map[idx]
                image_info[info_idx]['path'] = path

        return {
            'metadata': metadata,
            'image_info': image_info
        }
