"""
Task: transcribe
Pool: (none; submits whisper to cuda_pool)
Input:
    url_slug        str  mandatory url slug
    audio_path      str  path to the 16kHz mono WAV produced by extract_audio
    desc_task_ids   list[str] list of description task IDs
    metadata        dict  video metadata
Input (via dep_ enrichment from extract_audio):
    audio_path      str  path to the 16kHz mono WAV produced by extract_audio
Output:
    url_slug        str  url slug
    transcript      str  full transcript text
    desc_task_ids   list[str]
    metadata        dict
Creates: nothing
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

from modules.task_manager.task_manager import Task

log = logging.getLogger("task_transcribe")
POOL = None


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    config = context["config"]
    pool   = context["cuda_pool"]

    url_slug = input_data["url_slug"]
    dep_outputs = [
        v for k, v in input_data.items()
        if k.startswith("dep_") and isinstance(v, dict)
    ]
    desc_task_ids = input_data.get("desc_task_ids") or next(
        (v.get("desc_task_ids") for v in dep_outputs if v.get("desc_task_ids")),
        [],
    )
    metadata = input_data.get("metadata") or input_data.get("meta") or next(
        (v.get("metadata") for v in dep_outputs if v.get("metadata")),
        {},
    )

    # audio_path is injected by task_manager from the extract_audio dep output
    audio_path = next(
        (v.get("audio_path") for k, v in input_data.items()
         if k.startswith("dep_") and isinstance(v, dict) and "audio_path" in v),
        input_data.get("audio_path"),  # fallback for manual task creation
    )
    if not audio_path:
        raise ValueError("transcribe task: no audio_path in input or dep_ enrichment")

    log.info(f"Starting transcribe for slug: {url_slug}")

    def _run():
        with tempfile.TemporaryDirectory() as tmp:
            out_base = os.path.join(tmp, "out")
            r = subprocess.run([
                config["paths"]["whisper_bin"],
                "-m", config["paths"]["whisper_model"],
                "-f", audio_path,
                "-osrt", "-of", out_base,
                "--language", "auto",
                "-ng",
            ], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"whisper failed: {r.stderr}")
            srt = Path(out_base + ".srt")
            if not srt.exists():
                raise RuntimeError("whisper produced no output file")
            return srt.read_text(encoding="utf-8").strip()

    transcript = await pool.submit(_run, label=f"whisper:{Path(audio_path).name}")
    
    return {"url_slug": url_slug, "transcript": transcript, "desc_task_ids": desc_task_ids, "metadata": metadata}
