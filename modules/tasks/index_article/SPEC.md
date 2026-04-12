# tasks/index_article

## Purpose
Writes the assembled article Markdown to disk and uploads it to the RAG collection.

## Pool
none — pure async I/O

## Input
```
url_slug  str  (mandatory)
url       str  original article URL
filename  str  target markdown filename (set by extract_article_content)
content   str  full markdown content to write
```

## Output
```
url_slug  str  (mandatory)
status    str  "indexed"
filename  str  echoed filename
```

## Creates
Nothing.

## Imports From
- `task_manager`: `Task`
- `indexer`: `save_and_upload`

## Behavior Rules
- `replace_existing=True` always passed to `save_and_upload`
- Does not construct content or filename — both are provided by extract_article_content

## Must NOT
- Import from any fetcher or parser module
- Modify the content or filename received in input_data
