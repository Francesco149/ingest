import json
import subprocess

from tests.fixtures.synthetic_video import generate_synthetic_video_fixture


def duration(path):
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(probe.stdout.strip())


def test_synthetic_video_fixture_generation(tmp_path):
    reference = generate_synthetic_video_fixture(tmp_path / "video")
    video_path = tmp_path / "video" / "synthetic_video.mp4"
    audio_path = tmp_path / "video" / "audio_16k.wav"

    assert video_path.exists()
    assert audio_path.exists()
    assert reference["width"] == 960
    assert reference["height"] == 540
    assert reference["transcript"] == (
        "This is my stickman animation. Pay close attention to it."
    )
    assert len(list((tmp_path / "video" / "frames").glob("*.png"))) == 60

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() == "960,540"

    assert duration(tmp_path / "video" / "video_no_audio.mp4") >= 5.9
    assert duration(video_path) >= 5.9
    assert duration(audio_path) >= 5.9

    saved_reference = json.loads((tmp_path / "video" / "reference.json").read_text(encoding="utf-8"))
    assert saved_reference["expected_visual_events"][-1] == "Kai opens the red door."
