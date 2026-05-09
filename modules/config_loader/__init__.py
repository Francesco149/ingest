import logging
import os
from pathlib import Path
import tomllib

log = logging.getLogger("config_loader")

_config = None
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge overrides into base."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def get_config() -> dict:
    """
    Return the shared configuration dictionary.

    Load `config.example.toml` as the base, then merge either `INGEST_CONFIG`
    or the repo-local `config.toml` when present.
    """
    global _config
    if _config is not None:
        return _config

    example_path = PROJECT_ROOT / "config.example.toml"
    if example_path.exists():
        log.info(f"Loading base configuration from: {example_path}")
        with example_path.open("rb") as fh:
            _config = tomllib.load(fh)
    else:
        log.warning("config.example.toml not found; using empty base config")
        _config = {}

    config_path_str = os.environ.get("INGEST_CONFIG")
    if not config_path_str:
        local_config = PROJECT_ROOT / "config.toml"
        if local_config.exists():
            config_path_str = str(local_config)

    if not config_path_str:
        config_path_str = str(PROJECT_ROOT / "config.toml")

    log.info(f"Attempting to merge overrides from: {config_path_str}")
    try:
        with Path(config_path_str).open("rb") as fh:
            loaded_config = tomllib.load(fh)
        deep_merge(_config, loaded_config)
        log.info("Configuration merged successfully.")
    except FileNotFoundError:
        log.info("No override configuration file found. Using example defaults.")
    except Exception as exc:
        log.error(f"Failed to merge configuration: {exc}. Using example defaults.")

    def env_var(base: dict, keys: list[str]) -> None:
        for key in keys:
            value = os.environ.get(key.upper())
            if value:
                log.info(f"Overriding {key} from environment")
                base[key] = value

    env_var(
        _config["paths"],
        [
            "whisper_bin",
            "whisper_model",
            "yt_dlp_bin",
            "ffmpeg_bin",
            "ffprobe_bin",
        ],
    )

    return _config
