# Summarize Video Task

Generates a detailed semantic summary of a video segment by synthesizing transcript text and visual descriptions provided by specific task dependencies.

## Purpose
Synthesizes visual descriptions and transcripts into a coherent narrative summary of the video content.

## Pool
`vision`

## Input Schema
- `url_slug` (str): Required video identifier.
- `transcript` (list[dict[str, Any]]): The full transcript segments.
- `metadata` (dict): Video information (e.g., `title`, `tags`).
- `desc_task_ids` (list[str]): List of task IDs used to retrieve visual descriptions.

## Output Schema
- `reasoning_text` (str): The generated semantic summary.
- `url_slug` (str): The video identifier.
- `metadata` (dict): The original video metadata.

## Dependencies
- `download_video` (via `url_slug`)
- `describe_single_chunk` (via `desc_task_ids`)
- `transcribe` (via `transcript`)

## Behavior Rules
- Prompt text comes from `config["prompts"]["video_summarize"]`.
