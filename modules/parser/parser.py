import re
import logging
import trafilatura

log = logging.getLogger("parser")

from typing import Any

def _parse_vtt(vtt: str) -> list[dict[str, Any]]:
    segments = []
    seen_text = set()
    
    # Pattern to match VTT timestamp lines: 00:00:01.000 --> 00:00:04.000
    timestamp_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})')
    
    def parse_ts(ts_str: str) -> float:
        parts = ts_str.split(':')
        h = int(parts[0])
        m = int(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s

    current_segment = None
    
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT"):
            continue
            
        # Check if this line is a timestamp line
        ts_match = timestamp_pattern.search(line)
        if ts_match:
            if current_segment:
                text = " ".join(current_segment["text"]).strip()
                if text and text not in seen_text:
                    segments.append({
                        "start": current_segment["start"],
                        "end": current_segment["end"],
                        "text": text
                    })
                    seen_text.add(text)
            
            start_sec = parse_ts(ts_match.group(1))
            end_sec = parse_ts(ts_match.group(2))
            
            current_segment = {
                "start": start_sec,
                "end": end_sec,
                "text": []
            }
            continue

        # If it's not a timestamp line and not a numeric index line
        if not re.match(r'^\d+$', line):
            # Clean HTML tags if present
            cleaned = re.sub(r'<[^>]+>', '', line).strip()
            if cleaned and current_segment is not None:
                current_segment["text"].append(cleaned)
    
    # Handle last segment
    if current_segment:
        text = " ".join(current_segment["text"]).strip()
        if text and text not in seen_text:
            segments.append({
                "start": current_segment["start"],
                "end": current_segment["end"],
                "text": text
            })
            seen_text.add(text)
                    
    return segments

def recursive_split(text: str, max_chars: int, separators: list[str]) -> list[str]:
    """
    Recursively splits text into chunks of at most max_chars using a list of separators.
    """
    if len(text) <= max_chars:
        return [text]

    # Find the best separator to split on
    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            chunks = []
            current_chunk = ""
            
            for part in parts:
                # If adding this part (plus the separator) exceeds max_chars, 
                # we must start a new chunk.
                if len(current_chunk) + len(part) + len(sep) <= max_chars:
                    if current_chunk:
                        current_chunk += sep + part
                    else:
                        current_chunk = part
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    # If the part itself is larger than max_chars, split it further
                    if len(part) > max_chars:
                        sub_chunks = recursive_split(part, max_chars, separators)
                        chunks.extend(sub_chunks)
                        current_chunk = ""
                    else:
                        current_chunk = part
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Flatten any nested chunks from recursive calls
            final_chunks = []
            for c in chunks:
                if len(c) > max_chars:
                    final_chunks.extend(recursive_split(c, max_chars, separators))
                else:
                    final_chunks.append(c)
            return final_chunks

    # If no separators found, hard split by character
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

def extract_content(html: str) -> dict[str, str]:
    # Pre-process HTML to ensure <pre> blocks are properly newline-delimited
    html = re.sub(r'<pre>(.*?)</pre>', lambda m: f"<pre>\n{m.group(1).replace('\n', '<br/>')}\n</pre>", html, flags=re.DOTALL)
    
    text = trafilatura.extract(html, output_format='markdown', with_metadata=True)
    if text is None:
        return {"markdown": "", "title": "Unknown Title"}
    
    # Get the title from metadata
    try:
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata and metadata.title else "Unknown Title"
    except Exception:
        title = "Unknown Title"

    # Use recursive split to break down long text into manageable chunks
    chunks = recursive_split(text, max_chars=1000, separators=["\n\n", "\n", " ", ""])
            
    return {
        "markdown": "\n\n## (markdown chunk)\n\n".join(chunks),
        "title": title
    }
