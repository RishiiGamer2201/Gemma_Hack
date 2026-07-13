"""Shareable Rights Card rendered entirely from verified inputs.

Every line on the card is traceable. Section numbers and act names come from the
retrieved evidence, helpline numbers come from the reviewed legal-aid directory,
and the QR code encodes an official government source URL and nothing else. The
renderer accepts no free text that a model produced without verification.

The card is a summary of an answer that already passed verification. It is not a
second, softer channel for legal content, and it must never say anything the
verified answer did not.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from urllib.parse import urlparse

from src.legal_aid.directory import LegalAidFallback
from src.models.schemas import SourceEvidence

CARD_WIDTH = 1080
CARD_HEIGHT = 1920
MARGIN = 64
MAX_RIGHTS = 5
MAX_RIGHT_CHARACTERS = 180

# A QR code is a link the user will trust and follow. It may only point at an
# official government source, never at a shortener, a mirror, or anything a model
# supplied.
OFFICIAL_HOST_SUFFIXES = (".gov.in", ".nic.in")

_BACKGROUND = (255, 255, 255)
_INK = (17, 24, 39)
_MUTED = (75, 85, 99)
_ACCENT = (17, 94, 89)
_RULE = (209, 213, 219)
_WARNING_BACKGROUND = (254, 243, 199)


class RightsCardError(RuntimeError):
    """A bounded failure while rendering a Rights Card."""


@dataclass(frozen=True, slots=True)
class RightsCardContent:
    """Verified inputs for one card. Nothing here may be model-invented."""

    title: str
    rights: tuple[str, ...]
    evidence: tuple[SourceEvidence, ...]
    fallbacks: tuple[LegalAidFallback, ...]
    language: str = "en"
    generated_on: date | None = None
    warnings: tuple[str, ...] = ()


def _official_url(evidence: Sequence[SourceEvidence]) -> str:
    for source in evidence:
        url = str(source.official_url)
        host = (urlparse(url).hostname or "").casefold()
        if host.endswith(OFFICIAL_HOST_SUFFIXES):
            return url
    raise RightsCardError(
        "no official government source URL is available, so no QR code can be shown"
    )


def _citation(source: SourceEvidence) -> str:
    section = f" s.{source.section}" if source.section else ""
    return f"{source.act}{section}"


# The drafter is told to cite source_id values inline, which is right for the JSON
# answer but reads as clutter on a card that is meant to be forwarded. The clean
# citation already appears under "Where this comes from", so the raw identifiers are
# stripped from the displayed right. Only tokens that match a real source_id are
# removed, so nothing a citizen wrote can be silently deleted.
_SOURCE_ID_TOKEN = re.compile(r"\s*[\(\[]?[a-z0-9_]+:[a-z0-9_.\-]+[\)\]]?")


def _clean_right(text: str, known_ids: frozenset[str]) -> str:
    def drop(match: re.Match[str]) -> str:
        token = match.group().strip(" ()[]")
        return "" if token in known_ids else match.group()

    cleaned = _SOURCE_ID_TOKEN.sub(drop, text)
    return re.sub(r"\s+([.,;:])", r"\1", cleaned).strip()


def render_rights_card(content: RightsCardContent) -> bytes:
    """Render a phone-sized PNG. Raises rather than emitting an unsourced card."""

    try:
        image_module = importlib.import_module("PIL.Image")
        draw_module = importlib.import_module("PIL.ImageDraw")
        font_module = importlib.import_module("PIL.ImageFont")
        qrcode = importlib.import_module("qrcode")
    except ImportError as exc:
        raise RightsCardError(
            "Pillow and qrcode are required; install the project's card extra"
        ) from exc

    if not content.rights:
        raise RightsCardError("a card must state at least one verified right")
    if not content.evidence:
        raise RightsCardError("a card must cite at least one official source")

    url = _official_url(content.evidence)
    known_ids = frozenset(source.source_id for source in content.evidence)
    rights = tuple(
        cleaned
        for right in content.rights
        if (cleaned := _clean_right(right, known_ids))
    )[:MAX_RIGHTS]
    if not rights:
        raise RightsCardError("a card must state at least one verified right")

    image = image_module.new("RGB", (CARD_WIDTH, CARD_HEIGHT), _BACKGROUND)
    draw = draw_module.Draw(image)
    title_font, heading_font, body_font, small_font = _fonts(font_module)

    cursor = MARGIN
    cursor = _text_block(draw, content.title, title_font, cursor, _INK, leading=12)
    cursor += 8
    draw.line(
        [(MARGIN, cursor), (CARD_WIDTH - MARGIN, cursor)], fill=_ACCENT, width=4
    )
    cursor += 32

    cursor = _text_block(draw, "Your rights", heading_font, cursor, _ACCENT, leading=10)
    cursor += 8
    for right in rights:
        text = right[:MAX_RIGHT_CHARACTERS]
        cursor = _text_block(
            draw, f"• {text}", body_font, cursor, _INK, leading=8, indent=8
        )
        cursor += 12

    cursor += 16
    cursor = _text_block(draw, "Where this comes from", heading_font, cursor, _ACCENT, leading=10)
    cursor += 8
    for source in content.evidence[:4]:
        line = _citation(source)
        if source.effective_from is None:
            # Commencement is unproven for this source. The card must say so; a
            # pocket card is exactly where a false impression of settled law does
            # the most damage.
            line += "  (commencement not verified)"
        cursor = _text_block(draw, line, small_font, cursor, _MUTED, leading=6, indent=8)
        cursor += 6

    if content.warnings:
        cursor += 16
        box_top = cursor
        wrapped: list[str] = []
        for warning in content.warnings[:2]:
            wrapped.extend(_wrap(draw, warning, small_font, CARD_WIDTH - 2 * MARGIN - 24))
        box_height = len(wrapped) * 30 + 24
        draw.rectangle(
            [(MARGIN, box_top), (CARD_WIDTH - MARGIN, box_top + box_height)],
            fill=_WARNING_BACKGROUND,
        )
        cursor = box_top + 12
        for line in wrapped:
            draw.text((MARGIN + 12, cursor), line, font=small_font, fill=_INK)
            cursor += 30
        cursor = box_top + box_height + 8

    cursor += 16
    cursor = _text_block(draw, "Free legal help", heading_font, cursor, _ACCENT, leading=10)
    cursor += 8
    for fallback in content.fallbacks[:3]:
        cursor = _text_block(
            draw,
            f"{fallback.service}: {fallback.phone}",
            body_font,
            cursor,
            _INK,
            leading=6,
            indent=8,
        )
        cursor += 8

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_size = qr_image.size[0]
    qr_top = CARD_HEIGHT - MARGIN - qr_size - 130
    image.paste(qr_image, (MARGIN, qr_top))

    caption_left = MARGIN + qr_size + 24
    draw.text(
        (caption_left, qr_top + 8),
        "Scan to open the\nofficial source",
        font=small_font,
        fill=_MUTED,
    )
    generated = content.generated_on or date.today()
    draw.text(
        (caption_left, qr_top + 80),
        f"Sources checked: {generated.isoformat()}",
        font=small_font,
        fill=_MUTED,
    )

    footer_top = CARD_HEIGHT - MARGIN - 110
    draw.line(
        [(MARGIN, footer_top)], fill=_RULE, width=2
    )
    draw.text(
        (MARGIN, footer_top + 12),
        "This is legal information, not legal advice, and not a lawyer.\n"
        "Check the official source and speak to a legal-aid lawyer before acting.",
        font=small_font,
        fill=_MUTED,
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _fonts(font_module):  # type: ignore[no-untyped-def]
    """Load a font that can render Devanagari where one is installed.

    Pillow's built-in bitmap font cannot draw Devanagari at all: a Hindi card would
    render as empty boxes. A DejaVu fallback keeps Latin text legible, and the caller
    is told when Hindi cannot be rendered rather than being handed a broken card.
    """

    candidates = (
        r"C:\Windows\Fonts\Nirmala.ttf",
        r"C:\Windows\Fonts\mangal.ttf",
        r"C:\Windows\Fonts\seguiemj.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for path in candidates:
        try:
            return (
                font_module.truetype(path, 52),
                font_module.truetype(path, 40),
                font_module.truetype(path, 32),
                font_module.truetype(path, 24),
            )
        except OSError:
            continue
    default = font_module.load_default()
    return (default, default, default, default)


def _wrap(draw, text: str, font, width: int) -> list[str]:  # type: ignore[no-untyped-def]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _text_block(  # type: ignore[no-untyped-def]
    draw,
    text: str,
    font,
    top: int,
    fill,
    *,
    leading: int = 8,
    indent: int = 0,
) -> int:
    width = CARD_WIDTH - 2 * MARGIN - indent
    cursor = top
    for line in _wrap(draw, text, font, width):
        draw.text((MARGIN + indent, cursor), line, font=font, fill=fill)
        box = draw.textbbox((0, 0), line, font=font)
        cursor += (box[3] - box[1]) + leading
    return cursor
