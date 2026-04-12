# rag_client

## Purpose
OpenWebUI RAG API client — uploads files and adds them to a knowledge collection; deletes files by ID.

## Exports
```python
async def upload_to_rag(path: Path, config: dict, existing_file_id: str = None) -> str | None
async def delete_file(file_id: str, config: dict)
```

## Imports From
None — no internal dependencies.

## Behavior Rules
- `upload_to_rag`: POSTs multipart to `/api/v1/files/`, polls up to 10× (2s each) until `data.content` is populated, then POSTs to `/api/v1/knowledge/{collection}/file/add`
- Returns `file_id` on success, `None` on any exception (logs error but does not raise)
- `delete_file`: DELETEs from `/api/v1/files/{file_id}`; logs but does not raise on failure
- Auth header: `Authorization: Bearer {openwebui_key}`

## Must NOT
- Import from any internal module
- Raise exceptions to callers — all errors are logged and swallowed
