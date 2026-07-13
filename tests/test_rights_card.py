"""The Rights Card must render only verified content and link only to official sources."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.legal_aid.directory import LegalAidFallback
from src.models.schemas import SourceEvidence
from src.tools.rights_card import (
    RightsCardContent,
    RightsCardError,
    _clean_right,
    render_rights_card,
)

pytest.importorskip("PIL")
pytest.importorskip("qrcode")


def evidence(url: str = "https://www.indiacode.nic.in/example.pdf", **updates) -> SourceEvidence:
    payload = {
        "source_id": "code_on_wages_2019_en:section-17",
        "jurisdiction": "India",
        "act": "The Code on Wages, 2019",
        "section": "17",
        "excerpt": "All wages shall be paid within the prescribed wage period.",
        "status": "in_force",
        "priority": 3,
        "official_url": url,
        "retrieved_at": datetime(2026, 7, 12, tzinfo=UTC),
        "sha256": "a" * 64,
    }
    payload.update(updates)
    return SourceEvidence.model_validate(payload)


def fallback() -> LegalAidFallback:
    return LegalAidFallback(
        fallback_id="tele-law-14454",
        service="Tele-Law",
        scope="India",
        phone="14454",
        official_url="https://www.tele-law.in",
        verified_date=date(2026, 7, 12),
        source_sha256="b" * 64,
        description="Free pre-litigation legal advice.",
    )


def content(**updates) -> RightsCardContent:
    payload = {
        "title": "Unpaid wages",
        "rights": ("Your employer must pay wages within the wage period.",),
        "evidence": (evidence(),),
        "fallbacks": (fallback(),),
    }
    payload.update(updates)
    return RightsCardContent(**payload)


def test_a_valid_card_renders_a_png() -> None:
    png = render_rights_card(content())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_non_official_qr_url_is_refused() -> None:
    """The QR is a link the user will trust. It may only point at a government source."""

    for url in (
        "https://example.com/fake.pdf",
        "https://evil.gov.in.attacker.com/x",
        "https://bit.ly/abc",
    ):
        with pytest.raises(RightsCardError, match="official"):
            render_rights_card(content(evidence=(evidence(url=url),)))


def test_a_card_needs_at_least_one_right_and_one_source() -> None:
    with pytest.raises(RightsCardError):
        render_rights_card(content(rights=()))
    with pytest.raises(RightsCardError):
        render_rights_card(content(evidence=()))


def test_inline_source_ids_are_stripped_but_citizen_text_is_kept() -> None:
    known = frozenset({"code_on_wages_2019_en:section-17"})
    cleaned = _clean_right(
        "Wages must be paid on time (code_on_wages_2019_en:section-17).", known
    )
    assert "code_on_wages_2019_en" not in cleaned
    assert cleaned == "Wages must be paid on time."

    # A token that is not a real source id must be left untouched: it might be the
    # user's own words, and the card must never silently delete what they said.
    preserved = _clean_right("See clause a:b for the ratio 3:4.", frozenset())
    assert "ratio 3:4" in preserved


def test_a_card_from_only_source_id_rights_is_refused_not_blanked() -> None:
    """If stripping identifiers leaves nothing, fail rather than render an empty card."""

    with pytest.raises(RightsCardError):
        render_rights_card(
            content(rights=("code_on_wages_2019_en:section-17",))
        )
