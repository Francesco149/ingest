# parser

## Purpose
Text extraction from VTT subtitle files and raw HTML. No network I/O, no subprocesses.

## Exports
```python
def _parse_vtt(vtt: str) -> list[dict[str, Any]]
def extract_content(html: str) -> dict[str, str]
def recursive_split(text: str, max_chars: int, separators: list[str]) -> list[str]
```

## Imports From
None — no internal dependencies (`trafilatura` is a third-party library).

## Behavior Rules
- `_parse_vtt`: deduplicates subtitle lines, prefixes each with `[MM:SS]` timestamp; skips WEBVTT header and numeric index lines
- `extract_content`: runs `trafilatura.extract` with `output_format='markdown'`; passes result through `recursive_split` at 400-char max
- `recursive_split`: splits on `["\n\n", "\n", " ", ""]` in priority order; hard-splits by character as last resort

## Must NOT
- Perform any I/O or network calls
- Import from any other internal module