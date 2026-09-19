import re


def normalize_text(text: str) -> str:
    """Clean whitespace while retaining meaningful line and page structure."""
    lines = []
    previous_was_blank = False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        if not cleaned_line:
            if not previous_was_blank:
                lines.append("")
            previous_was_blank = True
        else:
            lines.append(cleaned_line)
            previous_was_blank = False
    return "\n".join(lines).strip()
