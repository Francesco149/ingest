"""
Task: describe_single_chunk
Pool: vision
Purpose: Extracts a clip from the video, samples frames, and captions it using llama-video. Produces one timestamped description block.
Input:
    video_path  str   path to the downloaded video file
    start_ts    int   clip start in seconds
    end_ts      int   clip end in seconds
    url         str   original source URL (for logging)
    url_slug    str   url slug (for logging) (mandatory)
    custom_prompt str (optional) custom prompt for the LLM
    retriable   bool  always True — transient llama-server errors are retried on restart
Output:
    description  str  "#### MM:SS - MM:SS\\n\\n{caption}"
    start_ts      int  echoed for deterministic ordering in index_video
    url           str  echoed URL
    url_slug      str  echoed url slug (mandatory)
Creates: nothing
"""

import logging
import os
import subprocess
import tempfile
import hashlib
from typing import Dict, Any

from modules.task_manager.task_manager import Task
POOL = "cuda"

log = logging.getLogger("task_describe_single_chunk")

DEFAULT_PROMPT = """Explain what happens in this video, no preamble, no outro.
This is part of a longer video, so don't say "at the end of the video" or
"the last scene", just explain what happens. No "the video shows/contains" either.
Don't overthink it, just loosely describe the action. IMPORTANT: If you see any text, signs, diagrams, or labels, describe them very clearly and verbatim."""


async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    from llama_video import Extractor, Preprocessor, Settings, get_preset
    from llama_video.client import LlamaServerClient

    # 1. Extract mandatory identifier
    video_path = input_data["video_path"]
    start_ts   = input_data["start_ts"]
    end_ts     = input_data["end_ts"]
    url        = input_data.get("url")
    url_slug   = input_data["url_slug"]
    config     = context["config"]
    pool       = context["vision_pool"]

    log.info(f"Starting describe_single_chunk for slug: {url_slug}")

    header = f"{start_ts // 60:02d}:{start_ts % 60:02d} - {end_ts // 60:02d}:{end_ts % 60:02d}"

    os.environ["LLAMA_SERVER_URL"] = config["api"]["llama_base"]
    os.environ["LLAMA_SERVER_TIMEOUT"] = str(config["api"]["llama_timeout"])
    settings     = Settings()
    client       = LlamaServerClient(settings.server)
    preset       = get_preset("default")
    extractor    = Extractor(settings.extractor)
    preprocessor = Preprocessor(settings.model)
    fps          = config["processing"]["fps"]

    prompt = input_data.get("custom_prompt", DEFAULT_PROMPT)

    with tempfile.TemporaryDirectory() as tmp_dir:
        clip_path = os.path.join(tmp_dir, f"clip_{start_ts}.mp4")
        subprocess.run([
            config["paths"]["ffmpeg_bin"],
            "-i", video_path,
            "-ss", str(start_ts),
            "-t",  str(end_ts - start_ts),
            "-vf", "scale=-1:540",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-y", clip_path,
        ], capture_output=True, check=True)

        try:
            frames      = await extractor.extract_frames_async(clip_path)
            video_input = preprocessor.process(frames, fps=fps)

            prompt_id = hashlib.sha256(f"{clip_path}{prompt}{start_ts}-{end_ts}".encode()).hexdigest()
            result = await client.caption_video(
                video_input,
                prompt=f"""
                    [{prompt_id}]
                    {prompt.strip()}
                """.strip(),
                preset=preset,
                max_tokens=8192,
                temperature=0.2,
            )
            await client.close()
            return {
                "description": f"#### {header}\n\n{result}",
                "start_ts": start_ts,
                "url": url,
                "url_slug": url_slug,
            }
        except Exception as e:
            await client.close()
            raise  # let task_manager mark FAILED and retry on next restart
