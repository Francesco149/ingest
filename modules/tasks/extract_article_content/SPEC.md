# tasks/extract_article_content

## Purpose
Parses raw article HTML into clean Markdown and creates the chunk_article task.

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
url_slug      str  url slug (mandatory)
```

## Creates
- `chunk_article` — one; content and metadata are passed directly in input_data

## Imports From
- `task_manager`: `Task`
- `parser`: `extract_content` (called via pool.submit)

## Behavior Rules
- Full markdown content is passed directly into `chunk_article` input_data
- `chunk_article` fans out summarization before `index_article`

## Must NOT
- Import from any fetcher module
- Perform any HTTP I/O — html is injected as input
