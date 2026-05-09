import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from tests.fixtures.synthetic_manga import _font, _text_center


WIDTH = 960
HEIGHT = 540
FPS = 10
DURATION_SECONDS = 6
TRANSCRIPT = "Ria sees the blue key. Kai opens the red door."


def _draw_frame(path: Path, frame_index: int):
    t = frame_index / FPS
    image = Image.new("RGB", (WIDTH, HEIGHT), (248, 250, 252))
    draw = ImageDraw.Draw(image)
    title_font = _font(34)
    label_font = _font(28)
    object_font = _font(30)

    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), outline=(15, 23, 42), width=4)
    draw.text((24, 20), "Synthetic video fixture", font=label_font, fill=(15, 23, 42))

    key_x = 700
    key_y = 190
    door_box = (710, 300, 890, 500)
    ria_x = int(90 + min(t / 3.0, 1.0) * 500)
    kai_x = int(150 + min(max(t - 3.0, 0.0) / 2.5, 1.0) * 520)

    draw.rounded_rectangle((key_x - 58, key_y - 32, key_x + 58, key_y + 32), radius=16, fill=(37, 99, 235), outline=(15, 23, 42), width=4)
    _text_center(draw, (key_x - 80, key_y - 68, key_x + 80, key_y - 34), "BLUE KEY", object_font)

    door_fill = (239, 68, 68) if t < 4.5 else (248, 113, 113)
    draw.rectangle(door_box, fill=door_fill, outline=(127, 29, 29), width=5)
    _text_center(draw, (720, 330, 880, 390), "RED DOOR", object_font)
    if t >= 4.5:
        draw.arc((745, 350, 855, 470), start=270, end=90, fill=(255, 255, 255), width=8)
        draw.text((735, 455), "OPEN", font=object_font, fill=(255, 255, 255))

    draw.ellipse((ria_x - 42, 255, ria_x + 42, 339), fill=(255, 255, 255), outline=(15, 23, 42), width=5)
    draw.line((ria_x, 340, ria_x, 430), fill=(15, 23, 42), width=7)
    draw.line((ria_x, 380, ria_x - 58, 430), fill=(15, 23, 42), width=7)
    draw.line((ria_x, 380, ria_x + 58, 430), fill=(15, 23, 42), width=7)
    draw.text((ria_x - 36, 442), "RIA", font=label_font, fill=(15, 23, 42))

    draw.ellipse((kai_x - 38, 78, kai_x + 38, 154), fill=(255, 255, 255), outline=(15, 23, 42), width=5)
    draw.line((kai_x, 155, kai_x, 238), fill=(15, 23, 42), width=7)
    draw.line((kai_x, 188, kai_x - 54, 235), fill=(15, 23, 42), width=7)
    draw.line((kai_x, 188, kai_x + 54, 235), fill=(15, 23, 42), width=7)
    draw.text((kai_x - 34, 247), "KAI", font=label_font, fill=(15, 23, 42))

    if t < 3.0:
        event = "RIA WALKS TOWARD THE BLUE KEY"
    elif t < 4.5:
        event = "RIA HAS THE BLUE KEY"
    else:
        event = "KAI OPENS THE RED DOOR"
    draw.rounded_rectangle((24, 466, 620, 520), radius=12, fill=(255, 255, 255), outline=(15, 23, 42), width=3)
    draw.text((42, 477), event, font=title_font, fill=(15, 23, 42))

    image.save(path)


def generate_synthetic_video_fixture(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for frame_index in range(FPS * DURATION_SECONDS):
        _draw_frame(frames_dir / f"frame_{frame_index:04d}.png", frame_index)

    speech_wav = output_dir / "speech.wav"
    audio_wav = output_dir / "audio_16k.wav"
    video_no_audio = output_dir / "video_no_audio.mp4"
    video_path = output_dir / "synthetic_video.mp4"

    espeak = shutil.which("espeak-ng")
    if not espeak:
        raise RuntimeError("espeak-ng is required to generate synthetic speech audio")
    subprocess.run([espeak, "-s", "145", "-w", str(speech_wav), TRANSCRIPT], check=True)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to generate synthetic video fixtures")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(speech_wav),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(audio_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(frames_dir / "frame_%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video_no_audio),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_no_audio),
            "-i",
            str(audio_wav),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(video_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    reference = {
        "video_path": str(video_path),
        "audio_path": str(audio_wav),
        "frame_dir": str(frames_dir),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "duration_seconds": DURATION_SECONDS,
        "transcript": TRANSCRIPT,
        "expected_visual_events": [
            "Ria walks toward the blue key.",
            "Ria has the blue key.",
            "Kai opens the red door.",
        ],
        "expected_summary": (
            "Ria moves toward a blue key, then has the key. "
            "Kai opens the red door."
        ),
    }
    (output_dir / "reference.json").write_text(json.dumps(reference, indent=2), encoding="utf-8")
    return reference
