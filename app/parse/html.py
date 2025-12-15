\
from bs4 import BeautifulSoup

def extract_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    # normalize whitespace
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)
