import asyncio
import logging
import httpx
from pathlib import Path

log = logging.getLogger("rag_client")

async def upload_to_rag(path: Path, config: dict, existing_file_id: str = None) -> str | None:
    base_url = config['api']['openwebui_base']
    api_key = config['api']['openwebui_key']
    collection = config['api']['openwebui_collection']
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        if existing_file_id:
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    await c.delete(f"{base_url}/api/v1/files/{existing_file_id}",
                                   headers=headers)
                log.info(f"[rag] deleted {existing_file_id}")
            except Exception as e:
                log.info(f"[rag] delete failed (ok): {e}")

        async with httpx.AsyncClient(timeout=30) as c:
            with open(path, "rb") as f:
                resp = await c.post(f"{base_url}/api/v1/files/",
                                    headers=headers,
                                    files={"file": (path.name, f, "text/plain")})
        resp.raise_for_status()
        file_id = resp.json()["id"]
        log.info(f"[rag] uploaded {file_id}")

        for attempt in range(10):
            await asyncio.sleep(2)
            async with httpx.AsyncClient(timeout=10) as c:
                check = await c.get(f"{base_url}/api/v1/files/{file_id}",
                                    headers=headers)
            if check.is_success and check.json().get("data", {}).get("content"):
                log.info(f"[rag] ready after {(attempt+1)*2}s")
                break

        async with httpx.AsyncClient(timeout=30) as c:
            r2 = await c.post(
                f"{base_url}/api/v1/knowledge/{collection}/file/add",
                headers={**headers, "Content-Type": "application/json"},
                json={"file_id": file_id},
            )
        if not r2.is_success:
            log.error(f"[rag] add failed {r2.status_code}: {r2.text}")
        r2.raise_for_status()
        log.info(f"[rag] added to collection")
        return file_id
    except Exception as e:
        log.error(f"[rag] upload failed: {e}")
        return None

async def delete_file(file_id: str, config: dict):
    base_url = config['api']['openwebui_base']
    api_key = config['api']['openwebui_key']
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.delete(f"{base_url}/api/v1/files/{file_id}", headers=headers)
        resp.raise_for_status()
        log.info(f"[rag] deleted file {file_id}")
    except Exception as e:
        log.error(f"[rag] delete failed for {file_id}: {e}")
