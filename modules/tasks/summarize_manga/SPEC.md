# SPEC: summarize_manga

## Purpose
Summarize manga gallery content, including metadata (titles, tags) and page-by-page descriptions, to generate a semantic search-optimized summary.

## Pool
vision

## Input
- `url_slug`: str (mandatory)
- `metadata`: dict containing gallery metadata (title, tags)
- `dep_*`: dict outputs from previous tasks containing 'descriptions' list

## Output
- `reasoning_text`: str (The LLM generated summary)
- `url_slug`: str
- `descriptions`: list of dicts
- `start_page`: int (The first page number)
