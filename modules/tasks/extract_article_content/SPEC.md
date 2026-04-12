# tasks/extract_article_content

## Purpose
Parses raw article HTML into clean Markdown and creates the index_article task.

## Pool
cpu

## Input (direct)
```
url   str  article URL
url_slug str (mandatory)
html  str  raw HTML fetched by download_article
note  str  optional user note
```

## Output
```
text_len      int  character count of extracted text
index_task_id str  ID of the created index_article task
url_slug      str (mandatory)
```

## Creates
- `index_article` — one; no dependencies (content is passed directly in input_data)

## Imports From
- `task_manager`: `Task`
- `parser`: `extract_content` (called via pool.submit)

## Behavior Rules
- Filename: `{date}-article-{domain}-{slug[:40]}.md` where slug is the last path segment of the URL
- Full markdown content is passed directly into `index_article` input_data (not via dep_ enrichment) because it is built inline here

## Must NOT
- Import from any fetcher module
- Perform any HTTP I/O — html is injected as input
