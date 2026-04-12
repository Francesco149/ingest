# tasks/describe_single_chunk

## Purpose
Extracts a clip from the video, samples frames, and captions it using llama-video. Produces one timestamped description block.

## Pool
cuda

## Input
```
video_path  str   path to the downloaded video
start_ts    int   clip start in seconds
end_ts      int   clip end in seconds
url         str   source URL (for logging)
url_slug    str   url slug (for logging) (mandatory)
custom_prompt str (optional) custom prompt for the LLM
retriable   bool  always True — transient llama-server errors are retried on restart
```

## Output
```
descriptions  str  "#### MM:SS - MM:SS\n\n{caption}"
start_ts      int  echoed for deterministic ordering in index_video
url           str  echoed URL
url_slug      str  echoed url slug (mandatory)
```

## Creates
Nothing.

## Imports From
- `task_manager`: `Task`
- `llama_video`, `llama_video.client`: imported inside `run()` (heavy import, GPU deps)

## Behavior Rules
- Clip is written to a `tempfile.TemporaryDirectory` that is cleaned up after captioning
- Clip filename within tmp: `clip_{start_ts}.mp4` — unique per task invocation
- `LLAMA_SERVER_URL` env var is set from `config["api"]["llama_base"]` before creating the client
- On exception: `client.close()` is called then the exception is re-raised so task_manager marks FAILED and retries on next restart
- `prompt_id` includes clip path, prompt, and timestamp range to prevent the LLM from reusing a cached response across chunks

## Must NOT
- Write clips outside a temporary directory
- Catch exceptions silently — must re-raise to allow retry
- Import llama_video at module level (import inside run())
