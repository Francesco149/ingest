# tasks/download_article

## Purpose
Fetches article HTML and fans out to extract_article_content. This is the correct entry point for article ingestion — engine.handle_article creates this task, not extract_article_content directly.

## Pool
download

## Input
```
url       str  normalized article URL
url_slug  str (mandatory) url slug (for logging)
note      str  optional user note
```

## Output
```
url       str  echoed for downstream dep_ enrichment
url_slug  str (mandatory) url slug (for logging)
html      str  raw HTML string
```

## Creates
- `extract_article_content` — one; dep: this task; receives url, html, note

## Imports From
- `fetcher_article`: `download_article`
- `task_manager`: `Task`

## Behavior Rules
- Passes `html` directly into `extract_article_content` input (not via dep_ enrichment) because HTML is large and dep_ enrichment stores it in output_data
- Raises on HTTP error — task will be marked FAILED and not retried (not retriable)

## Must NOT
- Parse or process HTML — that is parser's responsibility
- Import from `fetcher_video`, `fetcher_subtitles`, or any video task
