# tasks/summarize_text_chunk

## Purpose
Summarizes a single chunk of article text for semantic search.

## Pool
vision

## Input
```
text         str  text chunk to summarize
chunk_index  int  source chunk index
```

## Output
```
summary  str  semantic-search-oriented chunk summary
```

## Behavior Rules
- Prompt text comes from `config["prompts"]["text_chunk_summary"]`.
- LLM work runs under the `vision` pool so article chunk summaries respect
  reasoning-model concurrency limits.
