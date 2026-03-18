from app.pdf_processor import PdfProcessor


def test_drop_numeric_axis_block() -> None:
    assert PdfProcessor._should_drop_text_block("2019\n2020\n2021\n2022", chart_heavy_page=True) is True


def test_drop_chart_source_block() -> None:
    assert PdfProcessor._should_drop_text_block("Source: Wind, HSBC; Note: Data as of 10 Mar.", chart_heavy_page=True) is True


def test_keep_normal_paragraph_with_numbers() -> None:
    text = "The 2026 fiscal deficit is maintained at 4% of GDP, with newly issued government bonds totalling RMB11.89trn."
    assert PdfProcessor._should_drop_text_block(text, chart_heavy_page=False) is False


def test_drop_figure_title_on_chart_heavy_page() -> None:
    assert PdfProcessor._should_drop_text_block("1: Cross-city travel hit record highs", chart_heavy_page=True) is True


def test_keep_contact_block() -> None:
    text = "Erin Xin\nSenior Economist, Greater China\nerin.y.xin@hsbc.com.hk\n+852 2996 6975"
    assert PdfProcessor._should_drop_text_block(text, chart_heavy_page=False) is False


def test_drop_short_label_on_chart_heavy_page() -> None:
    assert PdfProcessor._should_drop_text_block("Economic activity", chart_heavy_page=True) is True


def test_keep_long_narrative_on_chart_heavy_page() -> None:
    text = (
        "The policy mix remains pragmatic and defensive, using existing buffers while gradually shifting more "
        "resources toward energy-independent and geopolitically diversified growth drivers."
    )
    assert PdfProcessor._should_drop_text_block(text, chart_heavy_page=True) is False
