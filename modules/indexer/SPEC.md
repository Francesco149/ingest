# indexer

## Purpose
Writes Markdown files to `knowledge_dir` and uploads them to the OpenWebUI RAG collection. Maintains `.index.json` as the SSOT for URL → file mappings.

## Exports
```python
def load_index(knowledge_dir: Path) -> dict
def save_index(knowledge_dir: Path, index: dict)
async def save_and_upload(url: str, filename: str, content: str, config: dict, knowledge_dir: Path, replace_existing: bool = False)
```

## Imports From
- `rag_client`: `upload_to_rag`, `delete_file`
- `fetcher_url`: `slug`

## Behavior Rules
- Index key: `slug(url)` (8-char SHA-1)
- `replace_existing=True`: deletes all previous local files and RAG entries for the same URL slug before writing the new one
- Index is read and written atomically per call (not held in memory between calls)
- `save_and_upload` writes the file first, then uploads — a crash between the two leaves an orphaned local file (acceptable, handled on next ingest with `replace_existing`)

## Must NOT
- Import from `engine`, `task_manager`, or any task module
- Cache `.index.json` in memory across calls — always read fresh
