import html
import re
from bs4 import BeautifulSoup

def normalize_email_body(content: str, is_html: bool = False) -> str:
    """
    Normalizes email body content (plain text or HTML) into clean, readable text.
    - Parses HTML and strips scripts, styles, and hidden structures.
    - Decodes HTML entities (e.g., &amp; -> &, &nbsp; -> ' ', &mdash; -> '—').
    - Removes soft hyphens (&shy;, \\u00ad) and non-printable/zero-width formatting artifacts.
    - Normalizes excessive whitespace while preserving line breaks and paragraph structure.
    """
    if not content or not isinstance(content, str):
        return ""

    has_html_tags = bool(re.search(r"<(html|head|body|p|div|br|table|tr|td|h[1-6]|span|a)\b", content, re.IGNORECASE))
    
    if is_html or has_html_tags:
        try:
            soup = BeautifulSoup(content, "html.parser")
            
            # Remove scripts, styles, heads, noscripts, svgs
            for tag in soup(["script", "style", "head", "noscript", "svg"]):
                tag.decompose()

            # Insert line breaks for block elements before extracting text
            for block in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "table", "blockquote"]):
                block.append(soup.new_string("\n"))

            for br in soup.find_all("br"):
                br.replace_with("\n")

            text = soup.get_text()
        except Exception:
            text = content
    else:
        text = content

    # 1. Unescape HTML entities
    text = html.unescape(text)

    # 2. Remove soft hyphens (\u00ad) and literal &shy; artifacts
    text = text.replace("\u00ad", "")
    text = re.sub(r"&shy;?", "", text, flags=re.IGNORECASE)

    # 3. Strip zero-width characters and normalize non-breaking spaces
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\u200b\ufeff\u200c\u200d]", "", text)

    # 4. Clean up line-by-line whitespace
    lines = [line.strip() for line in text.splitlines()]
    
    # 5. Compress multiple consecutive blank lines (limit to 2)
    cleaned_lines = []
    empty_count = 0
    for line in lines:
        if not line:
            empty_count += 1
            if empty_count <= 2:
                cleaned_lines.append("")
        else:
            empty_count = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
