# fetcher_url

## Purpose
Pure URL utilities — normalization, slug generation, content-type detection. No I/O, no subprocesses.

## Exports
```python
def slug(url: str) -> str
def normalize_url(url: str) -> str
def creator_slug(name: str) -> str
def is_video(url: str) -> bool
def is_manga(url: str) -> bool
```

## Imports From
None — no internal dependencies.

## Behavior Rules
- `slug`: SHA-1 of url, first 8 hex chars — used as stable per-URL file identifier
- `normalize_url`: YouTube variants (watch, shorts, youtu.be) → `https://www.youtube.com/watch?v={id}`; non-YouTube strips utm_*, si, pp, feature, ref, igshid
- `is_video`: matches youtube.com/watch, youtu.be/, youtube.com/shorts, and extensions .mp4 .mkv .webm .mov

## Must NOT
- Perform any network I/O or subprocess calls
- Import from any other internal module
