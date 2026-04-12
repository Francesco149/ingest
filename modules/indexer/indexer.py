import json
import logging
from pathlib import Path

from modules.rag_client.rag_client import upload_to_rag
from modules.fetcher_url.fetcher_url import slug

log = logging.getLogger("indexer")


def load_index(knowledge_dir: Path) -> dict:
    index_path = knowledge_dir / ".index.json"
    if index_path.exists():
        return json.loads(index_path.read_text())
    return {}


def save_index(knowledge_dir: Path, index: dict):
    index_path = knowledge_dir / ".index.json"
    index_path.write_text(json.dumps(index, indent=2))


async def save_and_upload(
    url: str,
    filename: str,
    content: str,
    config: dict,
    knowledge_dir: Path,
    replace_existing: bool = False,
):
    index   = load_index(knowledge_dir)
    url_key = slug(url)

    if replace_existing:
        from modules.rag_client.rag_client import delete_file
        for old_entry in index.get(url_key, []):
            old_path = Path(old_entry["file"])
            if old_path.exists():
                old_path.unlink()
            if old_entry.get("owui_file_id"):
                await delete_file(old_entry["owui_file_id"], config)
        index[url_key] = []

    path = knowledge_dir / filename
    path.write_text(content, encoding="utf-8")
    log.info(f"saved {path}")

    file_id = await upload_to_rag(path, config)

    if url_key not in index:
        index[url_key] = []

    index[url_key].append({"file": str(path), "owui_file_id": file_id, "filename": filename})
    save_index(knowledge_dir, index)
