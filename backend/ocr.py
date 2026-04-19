import re
from google.cloud import vision


def parse_receipt(image_bytes: bytes) -> dict:
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)

    if not response.full_text_annotation:
        return {"merchant": "", "total": 0.0, "date": "", "currency": "USD"}

    text = response.full_text_annotation.text
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    merchant = lines[0] if lines else ""

    # Last dollar amount on the receipt is typically the total
    amounts = re.findall(r'\$?\s*(\d+\.\d{2})', text)
    total = float(amounts[-1]) if amounts else 0.0

    date_match = re.search(
        r'(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text
    )
    date = date_match.group(1) if date_match else ""

    return {"merchant": merchant, "total": total, "date": date, "currency": "USD"}
