# tasks/chunk_article

## Purpose
Splits article Markdown into text chunks and creates chunk summarization tasks
plus the article-level reducer.

## Pool
none

## Input
```
url       str  original article URL
url_slug  str  url slug (mandatory)
title     str  article title
content   str  full article Markdown
```

## Output
```
chunk_count  int        number of created chunks
task_ids     list[str]  summarize_text_chunk task IDs
```

## Creates
- `summarize_text_chunk` — one per text chunk
- `summarize_article` — depends on all chunk summary tasks
