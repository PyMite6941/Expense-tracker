import re
from google.cloud import vision

_client = vision.ImageAnnotatorClient()


def parse_receipt(image_bytes: bytes) -> dict:
    image = vision.Image(content=image_bytes)
    response = _client.document_text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Cloud Vision error: {response.error.message}")

    if not response.full_text_annotation:
        return {"merchant": "", "total": 0.0, "date": "", "currency": "USD"}

    text = response.full_text_annotation.text
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    merchant = _extract_merchant(lines)
    total = _extract_total(text)
    date = _extract_date(text)

    return {"merchant": merchant, "total": total, "date": date, "currency": "USD"}


def _extract_merchant(lines: list) -> str:
    skip = re.compile(
        r'\d{1,5}\s+\w+\s+(st|ave|blvd|rd|dr|ln|way)\b'
        r'|\d{2}[:/]\d{2}'
        r'|^\d+$',
        re.IGNORECASE,
    )
    for line in lines[:5]:
        if not skip.search(line) and len(line) > 2:
            return line
    return lines[0] if lines else ""


def _extract_total(text: str) -> float:
    for line in text.splitlines():
        if re.search(r'\btotal\b', line, re.IGNORECASE):
            match = re.search(r'\$?\s*(\d+\.\d{2})', line)
            if match:
                return float(match.group(1))
    amounts = re.findall(r'\$?\s*(\d+\.\d{2})', text)
    return max((float(a) for a in amounts), default=0.0)


def _extract_date(text: str) -> str:
    match = re.search(
        r'\b(\d{4}-\d{2}-\d{2}|(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-]\d{2,4})\b',
        text,
    )
    return match.group(1) if match else ""
