from app.pdf_processor import PdfProcessor


def test_detect_appendix_page() -> None:
    texts = [
        "Disclosures & Disclaimer",
        "Issuer of report",
        "Legal entities as at 7 December 2024",
    ]
    assert PdfProcessor._is_disclaimer_page(texts) is True
