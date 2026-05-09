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
- Combines metadata and descriptions into a single text block.
- Creates a structured Markdown file and saves it in a sub-directory named after the gallery's slug.
- Uploads the file to the RAG knowledge base using `save_and_upload`.
- On failure, returns `success: False`.
