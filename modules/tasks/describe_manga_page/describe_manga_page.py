"""
Task: describe_manga_page
Pool: vision
Purpose: Describes manga images using a vision-capable LLM for semantic search.
Input:
    image_paths    List[str]  list of paths to the images to describe
    url            str       original source URL
    url_slug       str       original source slug (mandatory)
    custom_prompt  str       (optional) custom prompt for the vision model
    metadata       dict      (optional) metadata from manga
    start_page     int       the starting page number for this batch
    end_page       int       the ending page number for this batch
Output:
    descriptions   list[dict] the generated descriptions
    url            str       original source URL
    url_slug       str       original source slug (mandatory)
Creates: nothing
"""

import logging
import os
import hashlib
import base64
import cv2
import tempfile
from typing import Dict, Any, List

from modules.task_manager.task_manager import Task
from modules.llm_openai import chat

log = logging.getLogger("task_describe_manga_page")
POOL = "vision"



async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    url_slug = input_data["url_slug"]
    url = input_data.get("url")
    image_paths = input_data["image_paths"]
    config = context["config"]
    prompt_text = input_data.get("custom_prompt", config["prompts"]["manga_describe"]["user_template"])

    start_page = input_data["start_page"]
    end_page = input_data["end_page"]

    log.info(f"Starting describe_manga_page for slug: {url_slug}")
    log.info(f"Describing manga images: {image_paths}")

    descriptions = []

    window_paths = image_paths
    window_temp_files = []
    window_images_content = []

    try:
        for i, path in enumerate(window_paths):
            working_path = path
            if path.lower().endswith((".jpg", ".jpeg")):
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    temp_file_path = tmp.name
                    log.info(f"Converting {path} -> {temp_file_path}")
                img = cv2.imread(path)
                if img is None:
                    raise ValueError(f"Could not read image at {path}")
                cv2.imwrite(temp_file_path, img)
                working_path = temp_file_path
                window_temp_files.append(temp_file_path)
            
            with open(working_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            window_images_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

        current_prompt = prompt_text.format(start=start_page, end=end_page)
        
        system_msg = config["prompts"]["manga_describe"]["system"]
        payload = {
            "messages": [
                { "role": "system", "content": system_msg },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": current_prompt}] + window_images_content
                }
            ],
            "max_tokens": config["manga"]["vision_max_tokens"],
            "temperature": config["manga"]["vision_temperature"],
        }

        result = await chat(
            prompt=payload["messages"],
            temperature=config["manga"]["vision_temperature"],
            max_tokens=config["manga"]["vision_max_tokens"],
            config=config
        )

        log.info(f"Got description: {result[:50]}...")
        descriptions.append({
            "description": result,
            "start_page": start_page,
            "end_page": end_page,
            "url": url,
            "url_slug": url_slug
        })

    except Exception as e:
        log.error(f"Vision batch failed for window {start_page}-{end_page}: {e}")
        raise
    finally:
        for f in window_temp_files:
            if os.path.exists(f):
                os.remove(f)

    return {
        "descriptions": descriptions,
        "url": url,
        "url_slug": url_slug,
    }
