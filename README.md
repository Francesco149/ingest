⚠️ **WARNING: This code was mainly written with AI assistance and is intended as a personal ad hoc tool. Use with caution and review all code before deployment.**

# ingest

## Overview
`ingest` aims to be multimedia ingestion and processing pipeline designed to bridge the gap between raw digital media and actionable intelligence. The goal is to automate the lifecycle of content ingestion—transforming raw videos, audio, and web articles into structured, semantically enriched data. By leveraging computer vision, speech-to-text, and advanced NLP, the system creates a high-fidelity knowledge base optimized for RAG (Retrieval-Augmented Generation) indexing.

## Architecture
The system is built on a highly decoupled, asynchronous architecture designed for scale and resilience:

* **DAG-based Task Scheduler**: Instead of linear execution, tasks are organized as Directed Acyclic Graphs (DAGs). This allows the system to manage complex dependencies, ensuring that downstream tasks (like indexing) only trigger once upstream requirements (like transcription) are successfully met.
* **Specialized Worker Pools**: To prevent resource contention, the engine utilizes specialized worker pools tailored to specific hardware bottlenecks:
    * **Download Workers (I/O-bound)**: Dedicated to fetching remote assets (YouTube, web content, etc.) without blocking compute cycles.
    * **CPU Workers**: Dedicated to heavy text-based manipulation, Markdown orchestration, and parsing.
    * **CUDA Workers (GPU-accelerated)**: My 3080 10GB. Runs llama-video specifically for video understanding.
    * **Vision Workers (GPU-accelerated)**: My 7800xt 16b. LLM calls to llama.cpp running Gemma 26B A4B it APEX I Mini. Used for image understanding, and just normal reasoning text inference.
* **SQLite State Management**: A centralized SQLite database tracks the state of every task and asset. This ensures atomicity, provides a granular audit trail, and enables robust error recovery/resumption.

## Key Features
* **Multi-modal Video Intelligence**: Automated extraction including high-accuracy transcription (Youtube Captions or Whisper) and video understanding (currently using llama_video at 2fps) to capture deep semantic context.
* **Manga Semantic Search**: Advanced character, trope, and metadata identification through a multi-modal pipeline:
    * **Vision Analysis**: `describe_manga_page` uses vision LLMs to identify visual attributes and character traits.
    * **Textual Summarization**: `summarize_manga` aggregates batches of page-level metadata into semantic descriptions, to put the overarching narrative and tropes into context.
* **Article Parsing (WIP)**: Web content is extracted using `trafilatura` and converted to Markdown. This is still rough around the edges and is only reall useful as RAG context right now rather than human-centric reading.
* **Automated RAG Indexing**: Direct integration with OpenWebUI to ingest processed content into a retrieval-ready format.

## AI/ML Implementation
* **Vision Processing**: Leverages `llama_video` paired with `Qwen3.6 A3B` (with reasoning mode disabled) for high-fidelity, frame-level analysis.
* **Text/Reasoning**: Interacts with local or custom inference servers via generic OpenAI-compatible endpoints (e.g., `llama.cpp`, `vLLM`, or custom FastAPI endpoints).

## Module Structure
The project is organized into functional modules to ensure maintainability and scalability:
* `modules/fetcher_*`: Dedicated modules for content source scrapers (e.g., YouTube, Web, manga).
* `modules/tasks_*`: Atomic processing units (e.g., transcription, manga analysis, article extraction).
* `modules/parser/`: Handles HTML-to-Markdown conversion and content extraction logic.
* `modules/indexer/`: Manages the indexing and RAG upload process to OpenWebUI.
* `modules/utils/`: Shared utility functions for state management, logging, and configuration.

## Requirements & Dependencies
### System Requirements
* **Hardware**: CUDA-enabled GPU (highly recommended for Whisper and Vision tasks).
* **System Binaries**: `ffmpeg`, `yt-dlp`.

### Software Dependencies
* **Language**: Python 3.10+
* **Core Libraries**: `fastapi`, `uvicorn`, `httpx`, `trafilatura`, `youtube-transcript-api`, `opencv-python`.

## Getting Started

1. **Environment Setup**:
   Install the necessary Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration**: 
   Configure your environment via `config.toml` or `.env` files. Ensure your LLM endpoints (OpenAI/llama.cpp) are correctly mapped in the configuration to your local or remote inference server.

3. **Running the System**:
   The system is orchestrated through an API layer. To start the ingestion engine and the management API, execute:
   ```bash
   python run_api.py
   ```

4. **Adding Content**:
   Submit tasks through the API/Management layer to trigger the DAG-based ingestion pipeline.
