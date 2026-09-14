"""Los campos de Anki son HTML; estas funciones son la frontera con el texto
plano. Puras: solo `html` y `re`."""

import html
import re


def strip_html(value: str) -> str:
    """Collapse a field to a single line. For list rows, not for editing."""
    text = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(text).replace("\xa0", " ").split())


def to_plain_text(value: str) -> str:
    """Field value -> editable plain text, keeping the line structure.

    Anki stores fields as HTML, so line breaks live in <br> and block tags.
    Collapsing them the way strip_html does would silently flatten a card into
    one line the moment it was written back.
    """
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"</(p|div|li|tr)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def to_field_html(text: str) -> str:
    """Plain text -> what Anki stores. Escaped, so a stray < cannot become
    markup, with newlines as the <br> Anki actually renders."""
    return html.escape(text, quote=False).replace("\n", "<br>")
