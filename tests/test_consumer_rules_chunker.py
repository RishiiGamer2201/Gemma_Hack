from pathlib import Path

from src.corpus.chunker import chunk_gazette_rules_english
from src.corpus.extract import ExtractedDocument, ExtractedPage


def test_bilingual_bundled_gazette_yields_separate_english_instruments() -> None:
    document = ExtractedDocument(
        path=Path("consumer-rules.pdf"),
        parser="synthetic",
        pages=(
            ExtractedPage(
                1,
                "1. संक्षिप्त नाम और प्रारम्भ\n2. परिभाषाएं\n"
                "1. Short title and commencement.—These rules may be called "
                "the First Rules, 2020.\n"
                "2. Definitions.—Meaning of terms.\n"
                "3. Fees.—The following table applies:\n"
                "1. Table row one remains with rule three.\n"
                "4. Four lakh to eight lakh: Rs 200.\n"
                "Provided that the fee may be waived.\n"
                "4. Records.—Keep the record.\n",
            ),
            ExtractedPage(
                2,
                "अधिसूचना\nनई दिल्ली\nकेंद्रीय सरकार नियम बनाती है\n"
                "1. संक्षिप्त नाम और प्रारम्भ\n2. आवेदन\n"
                "1. Short title and commencement.—These rules may be called "
                "the Second Rules, 2020.\n"
                "2. Application.—These rules apply to the stated class.\n",
            ),
        ),
    )

    chunks = chunk_gazette_rules_english(
        document,
        source_id="consumer_bundle_hi_en",
        metadata={"language": "hi-en", "official_url": "https://law.gov.in/rules.pdf"},
    )

    assert [(chunk.metadata["instrument_index"], chunk.section_id) for chunk in chunks] == [
        (1, "1"),
        (1, "2"),
        (1, "3"),
        (1, "4"),
        (2, "1"),
        (2, "2"),
    ]
    fee_rule = chunks[2]
    assert "1. Table row one" in fee_rule.text
    assert "4. Four lakh to eight lakh" in fee_rule.text
    assert "Provided that" in fee_rule.text
    assert chunks[3].heading == "4. Records.—Keep the record."
    assert fee_rule.metadata["language"] == "en"
    assert fee_rule.metadata["source_language"] == "hi-en"
    assert fee_rule.metadata["translation_available_in_source"] is True
    assert "अधिसूचना" not in chunks[3].text
    assert chunks[0].metadata["instrument_title"] == "First Rules, 2020"
    assert chunks[4].metadata["instrument_title"] == "Second Rules, 2020"


def test_corrigendum_without_short_title_uses_conservative_fallback() -> None:
    document = ExtractedDocument(
        path=Path("corrigendum.pdf"),
        parser="synthetic",
        pages=(ExtractedPage(1, "CORRIGENDUM\nFor page 8 line 40, read (a)."),),
    )

    chunks = chunk_gazette_rules_english(
        document,
        source_id="consumer_corrigendum_hi_en",
        metadata={"language": "hi-en"},
    )

    assert len(chunks) == 1
    assert chunks[0].heading == "Preamble"
    assert "CORRIGENDUM" in chunks[0].text


def test_amendment_without_short_title_label_is_still_chunked() -> None:
    document = ExtractedDocument(
        path=Path("amendment.pdf"),
        parser="synthetic",
        pages=(
            ExtractedPage(
                1,
                "1. (1) These rules may be called the Example (Amendment) Rules, 2023.\n"
                "(2) They come into force on publication.\n"
                "2. In the principal rules, rule 4 is substituted.\n"
                "[भाग II—खण्ड 3(i)] भारत का राजपत्र : असाधारण\n",
            ),
        ),
    )

    chunks = chunk_gazette_rules_english(
        document,
        source_id="example_amendment_hi_en",
        metadata={"language": "hi-en"},
    )

    assert [chunk.section_id for chunk in chunks] == ["1", "2"]
    assert "भारत का राजपत्र" not in chunks[1].text


def test_money_in_a_strong_rule_heading_does_not_stop_later_rules() -> None:
    document = ExtractedDocument(
        path=Path("fee-rules.pdf"),
        parser="synthetic",
        pages=(
            ExtractedPage(
                1,
                "1. Short title and commencement.—These rules may be called the Fee Rules.\n"
                "2. Definitions.—The Act means the principal Act.\n"
                "3. Fees.—A fee of ten rupees shall be paid.\n"
                "4. Records.—Keep the records.\n",
            ),
        ),
    )

    chunks = chunk_gazette_rules_english(
        document,
        source_id="fee_rules_hi_en",
        metadata={"language": "hi-en"},
    )

    assert [chunk.section_id for chunk in chunks] == ["1", "2", "3", "4"]
    assert chunks[2].heading == "3. Fees.—A fee of ten rupees shall be paid."
