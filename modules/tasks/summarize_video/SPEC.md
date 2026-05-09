# Summarize Video Task

Generates a detailed semantic summary of a video segment by synthesizing transcript text and visual descriptions provided by specific task dependencies.

## Purpose
Synthesizes visual descriptions and transcripts into a coherent narrative summary of the video content.

## Pool
`vision`

## Input Schema
- `url_slug` (str): Required video identifier.
- `transcript` (list[dict[str, Any]] | str): The full transcript segments or
  transcript text. May also arrive via `dep_*` enrichment from `transcribe`.
- `metadata` / `meta` (dict): Video information (e.g., `title`, `tags`). May
  also arrive via `dep_*` enrichment from `transcribe`.
- `desc_task_ids` (list[str]): List of task IDs used to retrieve visual descriptions.

## Output Schema
- `reasoning_text` (str): The generated semantic summary.
- `url_slug` (str): The video identifier.
- `metadata` (dict): The original video metadata.

## Dependencies
- `describe_single_chunk` tasks are read from `task_manager.db` using
  `desc_task_ids`.
- `transcribe` is a dependency on the no-subtitles path and provides transcript,
  metadata, and description task IDs via dep enrichment.

## Behavior Rules
- Prompt text comes from `config["prompts"]["video_summarize"]`.
- Transcript segments are formatted as timestamped lines for LLM context.
- Visual descriptions are retrieved from completed description tasks and
  included alongside overlapping transcript text for each segment.
