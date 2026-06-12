"""
Email Parser — extracts expense data from receipt/order confirmation emails.
Used by the Email Import (Max) feature.

Connects via IMAP SSL, searches recent emails for transaction keywords,
and extracts merchant name, amount, currency, and date.
"""
import email
import imaplib
import logging
import re
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# Keywords that indicate a receipt/transaction email
_RECEIPT_KEYWORDS = [
    "receipt", "order confirmation", "payment confirmation", "invoice",
    "your order", "payment received", "you've been charged", "transaction",
    "booking confirmation", "purchase confirmation", "order summary",
    "billing statement", "payment processed",
]

# Regex patterns tried in order; first match wins.
# Group 1 must capture the numeric amount.
_AMOUNT_PATTERNS = [
    (r'(?:Total|Grand Total|Amount|Charged|Order Total)[:\s]+\$\s*(\d{1,6}(?:,\d{3})*(?:\.\d{2})?)', "USD"),
    (r'(?:Total|Grand Total|Amount|Charged|Order Total)[:\s]+USD\s*(\d{1,6}(?:,\d{3})*(?:\.\d{2})?)', "USD"),
    (r'(?:Total|Grand Total|Amount|Charged|Order Total)[:\s]+€\s*(\d{1,6}(?:[.,]\d{3})*(?:[.,]\d{2})?)', "EUR"),
    (r'(?:Total|Grand Total|Amount|Charged|Order Total)[:\s]+£\s*(\d{1,6}(?:,\d{3})*(?:\.\d{2})?)', "GBP"),
    (r'\$\s*(\d{1,6}(?:,\d{3})*\.\d{2})', "USD"),
    (r'USD\s*(\d{1,6}(?:,\d{3})*(?:\.\d{2})?)', "USD"),
    (r'€\s*(\d{1,6}(?:[.,]\d{3})*(?:[.,]\d{2})?)', "EUR"),
    (r'£\s*(\d{1,6}(?:,\d{3})*(?:\.\d{2})?)', "GBP"),
]

_CATEGORY_RULES: List[Tuple[List[str], str]] = [
    (["restaurant", "food", "cafe", "coffee", "pizza", "burger", "sushi",
      "doordash", "ubereats", "grubhub", "delivery", "groceries", "supermarket"], "Food"),
    (["amazon", "ebay", "etsy", "shop", "store", "retail", "walmart",
      "target", "best buy", "purchase"], "Shopping"),
    (["uber", "lyft", "airline", "flight", "hotel", "airbnb", "booking",
      "travel", "expedia", "tripadvisor", "transit", "train"], "Travel"),
    (["netflix", "spotify", "hulu", "disney", "apple", "subscription",
      "monthly plan", "annual plan", "membership"], "Subscriptions"),
    (["electric", "gas", "water", "internet", "phone", "utility",
      "bill", "comcast", "verizon", "at&t", "tmobile"], "Utilities"),
    (["doctor", "pharmacy", "medical", "health", "dental", "vision",
      "hospital", "clinic", "prescription"], "Healthcare"),
    (["course", "udemy", "coursera", "book", "kindle", "software",
      "education", "tuition"], "Education"),
]


# ── Email decoding helpers ─────────────────────────────────────────────────────

def _decode_str(s: str) -> str:
    parts = decode_header(s or "")
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out)


def _get_text_body(msg: email.message.Message) -> str:
    plain, html = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not plain:
                try:
                    plain = part.get_payload(decode=True).decode(errors="replace")
                except Exception:
                    pass
            elif ct == "text/html" and not html:
                try:
                    raw = part.get_payload(decode=True).decode(errors="replace")
                    html = re.sub(r"<[^>]+>", " ", raw)
                    html = re.sub(r"\s+", " ", html)
                except Exception:
                    pass
    else:
        try:
            raw = msg.get_payload(decode=True).decode(errors="replace")
            if msg.get_content_type() == "text/html":
                plain = re.sub(r"<[^>]+>", " ", raw)
            else:
                plain = raw
        except Exception:
            pass
    return plain or html


# ── Extraction helpers ─────────────────────────────────────────────────────────

def _extract_amount(text: str) -> Tuple[Optional[float], str]:
    for pattern, currency in _AMOUNT_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                amt = float(raw)
                if 0.01 <= amt <= 100_000:
                    return amt, currency
            except ValueError:
                pass
    return None, "USD"


def _extract_merchant(subject: str, sender: str) -> str:
    # Prefer "From" display name before the <email>
    m = re.match(r'^"?([^"<@\n]+)"?\s*<', sender)
    if m:
        name = m.group(1).strip().rstrip(",")
        if 2 < len(name) < 50:
            return name

    # Fallback: domain second-level label
    domain_m = re.search(r"@([\w.-]+)", sender)
    if domain_m:
        parts = domain_m.group(1).split(".")
        if len(parts) >= 2:
            return parts[-2].title()

    return subject[:40]


def _infer_category(subject: str, body_snippet: str) -> str:
    text = (subject + " " + body_snippet[:300]).lower()
    for keywords, category in _CATEGORY_RULES:
        if any(k in text for k in keywords):
            return category
    return "Other"


def _parse_date(date_str: str) -> str:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _is_receipt(subject: str, body_head: str) -> bool:
    text = (subject + " " + body_head[:400]).lower()
    return any(kw in text for kw in _RECEIPT_KEYWORDS)


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_expense_emails(
    imap_server: str,
    imap_port: int,
    email_address: str,
    password: str,
    days_back: int = 30,
    max_emails: int = 200,
) -> List[Dict]:
    """
    Connect to an IMAP mailbox, find receipt-like emails in the past
    *days_back* days, and return a list of candidate expense dicts.

    Each dict has the keys expected by ExpenseTracker.add_expenses():
        purchased, price, currency, tags, date, notes
    plus metadata keys prefixed with '_' for display in the UI.

    Raises ConnectionError on login failure, RuntimeError on other errors.
    """
    results: List[Dict] = []

    try:
        conn = imaplib.IMAP4_SSL(imap_server, imap_port)
    except Exception as exc:
        raise ConnectionError(f"Cannot connect to {imap_server}:{imap_port} — {exc}") from exc

    try:
        conn.login(email_address, password)
    except imaplib.IMAP4.error as exc:
        raise ConnectionError(f"IMAP login failed — {exc}") from exc

    try:
        conn.select("INBOX")
        since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        _, data = conn.search(None, f"SINCE {since_date}")
        all_ids: List[bytes] = data[0].split()

        # Process most-recent first, up to max_emails
        ids_to_scan = all_ids[-max_emails:] if len(all_ids) > max_emails else all_ids

        for num in reversed(ids_to_scan):
            try:
                _, msg_data = conn.fetch(num, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = _decode_str(msg.get("Subject", ""))
                sender  = msg.get("From", "")
                date_str = msg.get("Date", "")
                body = _get_text_body(msg)

                if not _is_receipt(subject, body):
                    continue

                amount, currency = _extract_amount(body)
                if amount is None:
                    amount, currency = _extract_amount(subject)
                if amount is None:
                    continue

                merchant = _extract_merchant(subject, sender)
                category = _infer_category(subject, body)
                expense_date = _parse_date(date_str)

                results.append({
                    "purchased": merchant,
                    "price": amount,
                    "currency": currency,
                    "tags": category,
                    "date": expense_date,
                    "notes": f"Imported from email: {subject[:80]}",
                    # Display-only metadata (stripped before saving)
                    "_subject": subject,
                    "_from": sender,
                })

            except Exception as exc:
                log.debug("Skipping message %s: %s", num, exc)

    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return results
