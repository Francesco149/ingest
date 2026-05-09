import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _find_font() -> str | None:
    candidates = [
        "/run/current-system/sw/share/X11/fonts/TTF/DejaVuSans.ttf",
        "/run/current-system/sw/share/fonts/truetype/DejaVuSans.ttf",
    ]
    candidates.extend(
        str(path)
        for root in Path("/nix/store").glob("*dejavu-fonts*/share/fonts")
        for path in root.rglob("DejaVuSans.ttf")
    )
    return next((path for path in candidates if Path(path).exists()), None)


def _font(size: int) -> ImageFont.ImageFont:
    font_path = _find_font()
    if font_path:
        return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def _text_center(draw: ImageDraw.ImageDraw, box, text: str, font, fill=(0, 0, 0)):
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=8, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x0, y0, x1, y1 = box
    draw.multiline_text(
        (x0 + (x1 - x0 - text_w) / 2, y0 + (y1 - y0 - text_h) / 2),
        text,
        font=font,
        fill=fill,
        spacing=8,
        align="center",
    )


def _speech_bubble(draw: ImageDraw.ImageDraw, box, tail, text: str, font):
    draw.rounded_rectangle(box, radius=34, fill=(255, 255, 255), outline=(0, 0, 0), width=4)
    x0, y0, x1, y1 = box
    draw.polygon([(x0 + 55, y1 - 5), (x0 + 18, y1 + 42), tail], fill=(255, 255, 255), outline=(0, 0, 0))
    _text_center(draw, box, text, font)


def _character(draw: ImageDraw.ImageDraw, cx: int, cy: int, name: str, font):
    draw.ellipse((cx - 38, cy - 78, cx + 38, cy - 2), fill=(255, 255, 255), outline=(0, 0, 0), width=4)
    draw.line((cx, cy, cx, cy + 95), fill=(0, 0, 0), width=5)
    draw.line((cx, cy + 35, cx - 58, cy + 72), fill=(0, 0, 0), width=5)
    draw.line((cx, cy + 35, cx + 58, cy + 72), fill=(0, 0, 0), width=5)
    draw.line((cx, cy + 95, cx - 42, cy + 150), fill=(0, 0, 0), width=5)
    draw.line((cx, cy + 95, cx + 42, cy + 150), fill=(0, 0, 0), width=5)
    draw.text((cx - 36, cy + 158), name, font=font, fill=(0, 0, 0))


def _draw_page(path: Path, page: dict):
    image = Image.new("RGB", (720, 1000), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(30)
    label_font = _font(22)
    bubble_font = _font(34)
    caption_font = _font(40)

    draw.rectangle((18, 18, 701, 981), outline=(0, 0, 0), width=4)
    draw.text((38, 35), f"VISIBLE PAGE {page['visible_page_number']}", font=title_font, fill=(0, 0, 0))
    draw.text((38, 78), f"STORY PAGE {page['story_page']}", font=title_font, fill=(0, 0, 0))

    panels = [(55, 130, 665, 395), (55, 430, 665, 710), (55, 745, 665, 945)]
    for panel in panels:
        draw.rectangle(panel, outline=(0, 0, 0), width=5)

    _character(draw, 175, 238, "RIA", label_font)
    _speech_bubble(draw, (315, 158, 640, 278), (282, 290), page["dialogue"][0], bubble_font)

    draw.rounded_rectangle((105, 485, 610, 658), radius=10, fill=(238, 238, 238), outline=(0, 0, 0), width=4)
    _text_center(draw, (120, 500, 595, 642), page["caption"], caption_font)

    _character(draw, 520, 835, "KAI", label_font)
    _speech_bubble(draw, (82, 775, 405, 895), (440, 888), page["dialogue"][1], bubble_font)

    image.save(path)


def generate_synthetic_manga_fixture(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = [
        {
            "story_page": 1,
            "visible_page_number": 99,
            "caption": "RIA FINDS A KEY",
            "dialogue": ["RIA: A KEY!", "KAI: HIDE IT!"],
            "expected": "Ria finds a key and Kai tells Ria to hide it.",
        },
        {
            "story_page": 2,
            "visible_page_number": 7,
            "caption": "DOOR OPENS",
            "dialogue": ["RIA: IT FITS!", "KAI: GO!"],
            "expected": "The key opens a door and Kai urges Ria forward.",
        },
        {
            "story_page": 3,
            "visible_page_number": 42,
            "caption": "STAR ROOM",
            "dialogue": ["RIA: STAR MAP!", "KAI: WE WIN!"],
            "expected": "Ria discovers a star map and Kai celebrates.",
        },
    ]
    image_paths = []
    for page in pages:
        image_path = output_dir / f"story_page_{page['story_page']:02d}.png"
        _draw_page(image_path, page)
        image_paths.append(str(image_path))

    reference = {
        "gallery_id": "synthetic-manga-001",
        "url": "https://example.test/g/synthetic-manga-001",
        "url_slug": "synthetic",
        "title": "Synthetic Key Quest",
        "tags": ["synthetic", "key", "door", "star"],
        "image_paths": image_paths,
        "pages": pages,
        "expected_summary_points": [
            "Ria finds a key.",
            "The key opens a door.",
            "Ria finds a star map.",
            "Visible page numbers 99, 7, and 42 are not story order.",
        ],
    }
    (output_dir / "reference.json").write_text(json.dumps(reference, indent=2), encoding="utf-8")
    return reference
