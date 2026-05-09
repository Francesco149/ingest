# config_loader

## Purpose
Loads repo configuration from `config.example.toml`, merges optional local
overrides, and applies a small set of environment-variable path overrides.

## Exports
```python
PROJECT_ROOT: Path
_config: dict | None

def deep_merge(base: dict, overrides: dict) -> dict
def get_config() -> dict
```

## Imports From
None.

## Behavior Rules
- `PROJECT_ROOT` resolves to the repository root.
- `get_config()` caches the merged config in module-global `_config`.
- Base config is loaded from `config.example.toml` when present.
- Override config is loaded from `INGEST_CONFIG` when set, otherwise local
  `config.toml` when present.
- Path-related environment variables override merged config values for:
  `whisper_bin`, `whisper_model`, `yt_dlp_bin`, `ffmpeg_bin`, `ffprobe_bin`.

## Must NOT
- Import from `engine`, `api`, or task modules
- Contain pool or task orchestration logic
