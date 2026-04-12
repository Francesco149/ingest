import os
import logging
import pathlib
import copy
import tomllib

log = logging.getLogger("config_loader")

_config = None

def deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merges two dictionaries."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base

def get_config() -> dict:
    """
    Returns the global configuration dictionary.
    Loads from config.example.toml as base, then merges overrides from INGEST_CONFIG
    or local config.toml.
    """
    global _config
    if _config is not None:
        return _config

    # 1. Start with the example/defaults file
    example_path = pathlib.Path("config.example.toml")
    if example_path.exists():
        log.info(f"Loading base configuration from: {example_path}")
        with open(example_path, "rb") as f:
            _config = tomllib.load(f)
    else:
        log.warning("config.example.toml not found! Using empty base.")
        _config = {}

    # 2. Determine override path
    config_path_str = os.environ.get("INGEST_CONFIG")
    if not config_path_str:
        local_config = pathlib.Path("config.toml")
        if local_config.exists():
            config_path_str = str(local_config.absolute())

    if not config_path_str:
        config_path_str = "/opt/ai-lab/ingest/config.toml"

    # 3. Merge overrides
    log.info(f"Attempting to merge overrides from: {config_path_str}")
    try:
        with open(config_path_str, "rb") as f:
            loaded_config = tomllib.load(f)
            deep_merge(_config, loaded_config)
        log.info("Configuration merged successfully.")
    except FileNotFoundError:
        log.info("No override configuration file found. Using defaults from example.")
    except Exception as e:
        log.error(f"Failed to merge configuration: {e}. Using defaults from example.")

    def env_var(base, keys):
        for key in keys:
            v = os.environ.get(key.upper())
            if v:
                log.info(f"Overriding {key} with env var with value {v}")
                base[key] = v

    env_var(_config["paths"], [
        "whisper_bin",
        "whisper_model",
        "yt_dlp_bin",
        "ffmpeg_bin",
        "ffprobe_bin",
    ])

    return _config
