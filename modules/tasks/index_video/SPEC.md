# tasks/index_video

## Purpose
Assembles all chunk descriptions and the transcript into a Markdown document and indexes it into the RAG collection.

## Pool
none — pure async I/O, runs in task_manager's event loop

## Input (direct)
```
url         str              original video URL
url_slug    str              mandatory slug for the URL
sub_result  tuple | None     (transcript_text, source) if subs were found; None otherwise
meta        dict             video metadata from yt-dlp
```

## Input (via dep_ enrichment)
```
From describe_single_chunk deps:  {descriptions: str, start_ts: int}
From transcribe dep (if present): {transcript: str}
```

## Output
```
filename  str  written markdown filename
url_slug  str  mandatory slug
```

## Creates
Nothing.

## Imports From
- `task_manager`: `Task`
- `indexer`: `save_and_upload`

## Behavior Rules
- Collects chunk deps: all `dep_*` values that are dicts containing `"descriptions"` key
- Sorts chunk deps by `start_ts` ascending before joining — ordering is deterministic
- Transcript priority: whisper `dep_*` enrichment first; `sub_result[0]` fallback
- Filename: `{title_part}-{url_slug}.md (where title_part is title[:80])`
- `replace_existing=True` is always passed to `save_and_upload`

## Must NOT
- Import from any fetcher module
- Re-derive the URL slug or path — uses `task.id[:8]` for uniqueness in the filename
