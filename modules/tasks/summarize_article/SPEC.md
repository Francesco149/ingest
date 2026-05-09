# tasks/summarize_article

## Purpose
Reduces chunk summaries into one article summary and creates `index_article`.

## Pool
none

## Input
```
url       str  original article URL
url_slug  str  url slug (mandatory)
title     str  article title
content   str  full article Markdown
dep_*     dict summarize_text_chunk outputs containing summary
```

## Output
```
url_slug  str  url slug (mandatory)
summary   str  final article summary
```

## Creates
- `index_article` — one task with article content and final summary

## Behavior Rules
- If there is one chunk summary, use it directly.
- If there are multiple chunk summaries, combine them with
  `config["prompts"]["article_summary"]`.
