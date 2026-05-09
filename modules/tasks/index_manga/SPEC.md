# tasks/index_manga

## Purpose
Indexes manga gallery content into the RAG knowledge base.

## Pool
cpu

## Input
```
gallery_id    str  manga gallery ID
metadata      dict  gallery metadata (title, tags)
url_slug      str  (mandatory) The Primary Identifier.
url           str  original source URL
dep_*         dict  task outputs containing 'reasoning_text' and 'transcript_text'
```

## Output
```
url_slug  str  (mandatory)
filename str (optional)
```

## Creates
Nothing.

## Behavior Rules
- Collects `reasoning_text` and `transcript_text` from all `dep_*` dictionaries.
- Sorts reasoning and transcript parts independently by `start_page` before
  joining each group with `---` separators.
- Filename is `{best_title[:90]}-{url_slug}.md`, falling back to
  `{YYYY-MM-DD}-{url_slug}.md` when no title exists.
- Uploads via `save_and_upload(..., replace_existing=True)`.
- Raises when required dependency text is missing or indexing fails.
