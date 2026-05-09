import json
import struct
import zlib
from pathlib import Path


FONT = {
    " ": ["000", "000", "000", "000", "000", "000", "000"],
    "!": ["1", "1", "1", "1", "1", "0", "1"],
    "'": ["1", "1", "0", "0", "0", "0", "0"],
    ",": ["0", "0", "0", "0", "0", "1", "1"],
    "-": ["000", "000", "000", "111", "000", "000", "000"],
    ".": ["0", "0", "0", "0", "0", "0", "1"],
    ":": ["0", "1", "0", "0", "0", "1", "0"],
    "?": ["111", "001", "001", "011", "010", "000", "010"],
    "0": ["111", "101", "101", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "010", "010", "111"],
    "2": ["111", "001", "001", "111", "100", "100", "111"],
    "3": ["111", "001", "001", "111", "001", "001", "111"],
    "4": ["101", "101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "100", "111", "001", "001", "111"],
    "6": ["111", "100", "100", "111", "101", "101", "111"],
    "7": ["111", "001", "001", "010", "010", "010", "010"],
    "8": ["111", "101", "101", "111", "101", "101", "111"],
    "9": ["111", "101", "101", "111", "001", "001", "111"],
    "A": ["010", "101", "101", "111", "101", "101", "101"],
    "B": ["110", "101", "101", "110", "101", "101", "110"],
    "C": ["011", "100", "100", "100", "100", "100", "011"],
    "D": ["110", "101", "101", "101", "101", "101", "110"],
    "E": ["111", "100", "100", "110", "100", "100", "111"],
    "F": ["111", "100", "100", "110", "100", "100", "100"],
    "G": ["011", "100", "100", "101", "101", "101", "011"],
    "H": ["101", "101", "101", "111", "101", "101", "101"],
    "I": ["111", "010", "010", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "001", "101", "101", "010"],
    "K": ["101", "101", "110", "100", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101", "101", "101"],
    "N": ["101", "111", "111", "111", "111", "111", "101"],
    "O": ["010", "101", "101", "101", "101", "101", "010"],
    "P": ["110", "101", "101", "110", "100", "100", "100"],
    "Q": ["010", "101", "101", "101", "111", "011", "001"],
    "R": ["110", "101", "101", "110", "110", "101", "101"],
    "S": ["011", "100", "100", "010", "001", "001", "110"],
    "T": ["111", "010", "010", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "101", "101", "010"],
    "W": ["101", "101", "101", "101", "111", "111", "101"],
    "X": ["101", "101", "101", "010", "101", "101", "101"],
    "Y": ["101", "101", "101", "010", "010", "010", "010"],
    "Z": ["111", "001", "001", "010", "100", "100", "111"],
}


def _set_px(buf, width, height, x, y, color):
    if 0 <= x < width and 0 <= y < height:
        idx = (y * width + x) * 3
        buf[idx : idx + 3] = bytes(color)


def _rect(buf, width, height, x0, y0, x1, y1, color, fill=True):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if fill or x in (x0, x1) or y in (y0, y1):
                _set_px(buf, width, height, x, y, color)


def _line(buf, width, height, x0, y0, x1, y1, color):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _set_px(buf, width, height, x0, y0, color)
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _ellipse(buf, width, height, cx, cy, rx, ry, color, fill=False):
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            value = ((x - cx) * (x - cx)) / (rx * rx) + ((y - cy) * (y - cy)) / (ry * ry)
            if (fill and value <= 1.0) or (not fill and 0.86 <= value <= 1.12):
                _set_px(buf, width, height, x, y, color)


def _text(buf, width, height, x, y, text, color=(0, 0, 0), scale=3):
    cursor = x
    for char in text.upper():
        glyph = FONT.get(char, FONT["?"])
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    _rect(
                        buf,
                        width,
                        height,
                        cursor + gx * scale,
                        y + gy * scale,
                        cursor + gx * scale + scale - 1,
                        y + gy * scale + scale - 1,
                        color,
                    )
        cursor += (len(glyph[0]) + 1) * scale


def _write_png(path, width, height, pixels):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + pixels[y * width * 3 : (y + 1) * width * 3] for y in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _draw_page(path, page):
    width, height = 720, 1000
    white = (255, 255, 255)
    black = (0, 0, 0)
    gray = (225, 225, 225)
    pixels = bytearray(white * width * height)

    _rect(pixels, width, height, 18, 18, width - 19, height - 19, black, fill=False)
    _text(pixels, width, height, 38, 38, f"VISIBLE PAGE {page['visible_page_number']}", black, scale=3)
    _text(pixels, width, height, 38, 78, f"STORY PAGE {page['story_page']}", black, scale=3)

    panels = [(55, 130, 665, 395), (55, 430, 665, 710), (55, 745, 665, 945)]
    for panel in panels:
        _rect(pixels, width, height, *panel, black, fill=False)

    _ellipse(pixels, width, height, 175, 245, 55, 55, black)
    _line(pixels, width, height, 175, 300, 175, 355, black)
    _line(pixels, width, height, 175, 325, 125, 365, black)
    _line(pixels, width, height, 175, 325, 225, 365, black)
    _line(pixels, width, height, 175, 355, 140, 390, black)
    _line(pixels, width, height, 175, 355, 210, 390, black)
    _ellipse(pixels, width, height, 455, 215, 165, 58, black)
    _text(pixels, width, height, 330, 193, page["dialogue"][0], black, scale=4)

    _rect(pixels, width, height, 105, 475, 610, 660, gray, fill=True)
    _rect(pixels, width, height, 105, 475, 610, 660, black, fill=False)
    _text(pixels, width, height, 130, 520, page["caption"], black, scale=4)

    _ellipse(pixels, width, height, 520, 840, 48, 48, black)
    _line(pixels, width, height, 520, 888, 520, 930, black)
    _line(pixels, width, height, 520, 905, 482, 935, black)
    _line(pixels, width, height, 520, 905, 558, 935, black)
    _ellipse(pixels, width, height, 235, 835, 155, 58, black)
    _text(pixels, width, height, 120, 813, page["dialogue"][1], black, scale=4)

    _write_png(path, width, height, pixels)


def generate_synthetic_manga_fixture(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = [
        {
            "story_page": 1,
            "visible_page_number": 99,
            "caption": "RIN FINDS A KEY",
            "dialogue": ["RIN: A KEY!", "KAI: HIDE IT!"],
            "expected": "Rin finds a key and Kai tells Rin to hide it.",
        },
        {
            "story_page": 2,
            "visible_page_number": 7,
            "caption": "DOOR OPENS",
            "dialogue": ["RIN: IT FITS!", "KAI: GO!"],
            "expected": "The key opens a door and Kai urges Rin forward.",
        },
        {
            "story_page": 3,
            "visible_page_number": 42,
            "caption": "MOON ROOM",
            "dialogue": ["RIN: MOON MAP!", "KAI: WE WON!"],
            "expected": "Rin discovers a moon map and Kai celebrates.",
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
        "tags": ["synthetic", "key", "door", "moon"],
        "image_paths": image_paths,
        "pages": pages,
        "expected_summary_points": [
            "Rin finds a key.",
            "The key opens a door.",
            "Rin finds a moon map.",
            "Visible page numbers 99, 7, and 42 are not story order.",
        ],
    }
    (output_dir / "reference.json").write_text(json.dumps(reference, indent=2), encoding="utf-8")
    return reference
