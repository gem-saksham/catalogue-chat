from pathlib import Path
from parse.html import extract_html_text
from parse.pdf import extract_pdf_text
from pypdf import PdfWriter


def test_extract_html_text_removes_scripts_and_empty_lines():
    html = """
    <html><head><script>alert('x')</script><style>body{}</style></head>
    <body><h1>Title</h1><p>Paragraph</p><noscript>ignore</noscript></body></html>
    """
    text = extract_html_text(html)
    assert "alert" not in text
    assert "ignore" not in text
    assert "Title" in text and "Paragraph" in text
    # Ensure no blank lines remain
    assert "\n\n" not in text


def test_extract_pdf_text_reads_simple_pdf(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    text = extract_pdf_text(pdf_path)
    assert isinstance(text, str)
