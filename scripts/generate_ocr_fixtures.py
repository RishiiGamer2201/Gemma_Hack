"""Generate deterministic synthetic printed and phone-style OCR benchmark notices."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

NOTICE_LINES = (
    "LEGAL NOTICE",
    "Date: 13 July 2026",
    "To: The Tenant",
    "Subject: Security deposit records",
    "Please preserve the rent agreement, payment receipts,",
    "bank statements, photographs, and all written messages.",
    "This synthetic notice is for offline OCR testing only.",
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    ):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def build_notice() -> Image.Image:
    image = Image.new("RGB", (1600, 2200), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((85, 85, 1515, 2115), outline="#1f2937", width=5)
    y = 180
    for index, line in enumerate(NOTICE_LINES):
        font = _font(72 if index == 0 else 48)
        draw.text((150, y), line, fill="black", font=font)
        y += 150 if index == 0 else 115
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".runtime/ocr_samples"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    printed = build_notice()
    printed.save(args.output_dir / "printed_notice.png", optimize=True)

    phone = Image.new("RGB", (1900, 2500), "#374151")
    photographed = printed.resize((1400, 1925)).rotate(
        4.0, resample=Image.Resampling.BICUBIC, expand=True, fillcolor="#d1d5db"
    )
    photographed = photographed.filter(ImageFilter.GaussianBlur(radius=0.65))
    x = (phone.width - photographed.width) // 2
    y = (phone.height - photographed.height) // 2
    phone.paste(photographed, (x, y))
    phone.save(args.output_dir / "phone_notice.jpg", quality=68, optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
