"""Bank-statement CSV import: parse, clean, categorize, de-duplicate.

Pure Python (stdlib only) so it works for the CLI, the Streamlit UI, the hosted
mode and tests alike. Nothing here reads or writes the user's data file —
`ExpenseTracker.preview_bank_statement` / `commit_bank_import` do that.

Pipeline:  raw bytes -> rows -> header detection -> Transaction list
           -> categorize (user rules > your own history > bank's category
              > built-in keywords) -> mark duplicates against existing data.

Sign convention throughout: ``amount < 0`` is money OUT (an expense),
``amount > 0`` is money IN (income).
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

UNCATEGORIZED = "Uncategorized"

# ── Header detection ─────────────────────────────────────────────────────────
# Normalised header text (lowercase, alphanumerics only) -> role. Exact matches
# win over substring matches so "Amount" never loses to "Balance amount".
HEADER_ALIASES: Dict[str, Tuple[str, ...]] = {
    "date": ("date", "transactiondate", "transdate", "posteddate", "postingdate",
             "bookingdate", "valuedate", "dateposted", "completeddate", "startdate",
             "buchungstag", "datum", "valuta", "fecha", "dateoperation", "dateopration", "data"),
    "description": ("description", "transactiondescription", "payee", "merchant",
                    "name", "details", "memo", "narrative", "particulars",
                    "originaldescription", "reference", "verwendungszweck", "buchungstext",
                    "beguenstigter", "concepto", "libelle", "libell", "descripcion"),
    "amount": ("amount", "transactionamount", "amountusd", "amountgbp", "amounteur",
               "netamount", "value", "betrag", "importe", "montant", "bedrag"),
    "debit": ("debit", "debits", "debitamount", "withdrawal", "withdrawals",
              "withdrawalamount", "moneyout", "paidout", "outflow", "spent"),
    "credit": ("credit", "credits", "creditamount", "deposit", "deposits",
               "depositamount", "moneyin", "paidin", "inflow", "received"),
    "type": ("type", "transactiontype", "crdr", "drcr", "debitcredit",
             "creditdebitindicator"),
    "category": ("category", "transactioncategory"),
    "currency": ("currency",),
}
# Headers that contain an alias but must never be mistaken for it.
HEADER_BLOCKLIST = ("balance", "runningbalance", "checkornumber", "checknumber")

DATE_FORMATS_MDY = ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y")
DATE_FORMATS_DMY = ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y", "%d.%m.%y")
DATE_FORMATS_UNAMBIGUOUS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%d %b %Y",
                            "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%d-%b-%Y",
                            "%d-%b-%y", "%b %d %Y")

# ── Built-in categorization ──────────────────────────────────────────────────
# Matched as whole words against the cleaned description, longest keyword
# first, so "uber eats" (Dining) beats "uber" (Transport).
DEFAULT_RULES: Dict[str, Tuple[str, ...]] = {
    "Groceries": ("whole foods", "wholefds", "trader joe", "safeway", "kroger", "aldi", "lidl",
                  "tesco", "sainsbury", "asda", "waitrose", "costco", "publix",
                  "wegmans", "grocery", "groceries", "supermarket", "market basket",
                  "food lion", "heb", "instacart", "sprouts", "morrisons", "coles",
                  "woolworths", "loblaws"),
    "Dining": ("uber eats", "doordash", "grubhub", "deliveroo", "just eat",
               "starbucks", "mcdonald", "chipotle", "dunkin", "subway", "pizza",
               "restaurant", "cafe", "coffee", "taco bell", "wendy", "burger",
               "kfc", "domino", "panera", "chick fil a", "sweetgreen", "bar",
               "grill", "diner", "bakery", "tst", "toast"),
    "Transport": ("uber", "lyft", "taxi", "metro", "transit", "mta", "tfl",
                  "parking", "toll", "train", "amtrak", "bus", "bart", "caltrain",
                  "citibike"),
    "Fuel": ("shell", "chevron", "exxon", "mobil", "bp", "texaco", "arco",
             "sunoco", "valero", "speedway", "fuel", "gas station", "petrol"),
    "Subscriptions": ("netflix", "spotify", "hulu", "disney plus", "disneyplus",
                      "hbo", "max com", "youtube premium", "apple com bill",
                      "icloud", "google storage", "amazon prime", "prime video",
                      "audible", "patreon", "chatgpt", "openai", "github",
                      "dropbox", "adobe", "microsoft 365", "paramount", "peacock"),
    "Shopping": ("amazon", "amzn", "target", "walmart", "ebay", "etsy", "best buy",
                 "ikea", "home depot", "lowe", "macy", "nordstrom", "zara", "h m",
                 "uniqlo", "nike", "apple store", "shein", "temu", "aliexpress"),
    "Utilities": ("electric", "electricity", "water", "sewer", "pg e", "con ed",
                  "comcast", "xfinity", "verizon", "at t", "t mobile", "spectrum",
                  "internet", "utility", "utilities", "power", "energy", "vodafone",
                  "british gas", "octopus energy"),
    "Housing": ("rent", "mortgage", "hoa", "landlord", "property management",
                "apartments", "realty"),
    "Health": ("pharmacy", "cvs", "walgreens", "rite aid", "boots", "doctor",
               "dental", "dentist", "clinic", "hospital", "medical", "gym",
               "fitness", "planet fitness", "optometrist", "health"),
    "Entertainment": ("steam", "playstation", "xbox", "nintendo", "cinema", "amc",
                      "regal", "ticketmaster", "eventbrite", "movie", "theater",
                      "theatre", "concert", "bowling"),
    "Travel": ("airline", "airlines", "delta", "united", "american air",
               "southwest", "jetblue", "ryanair", "easyjet", "british airways",
               "airbnb", "hotel", "marriott", "hilton", "hyatt", "expedia",
               "booking com", "vrbo"),
    "Insurance": ("insurance", "geico", "progressive", "allstate", "state farm"),
    "Fees": ("fee", "overdraft", "interest charge", "service charge", "atm fee",
             "late fee", "finance charge"),
    "Education": ("tuition", "university", "college", "school", "coursera",
                  "udemy", "textbook"),
    "Transfers": ("transfer", "venmo", "zelle", "paypal", "cash app", "wise",
                  "revolut", "payment thank you", "autopay", "credit card payment"),
}
# Money IN gets its own, much smaller vocabulary.
DEFAULT_INCOME_RULES: Dict[str, Tuple[str, ...]] = {
    "Salary": ("payroll", "salary", "direct dep", "direct deposit", "wages", "paycheck",
               "adp", "gusto"),
    "Interest": ("interest", "dividend"),
    "Refund": ("refund", "return", "reversal", "cashback", "cash back"),
    "Transfers": ("transfer", "venmo", "zelle", "paypal", "cash app"),
}

# Noise stripped from descriptions before display / matching.
_NOISE_PREFIXES = re.compile(
    r"^(pos\s+|purchase\s+|debit card purchase\s+|card purchase\s+|"
    r"recurring payment\s+|checkcard\s+|visa\s+|dbt crd\s+|ach\s+debit\s+|"
    r"ach\s+|sq\s*\*\s*|tst\s*\*\s*|sp\s*\*?\s*|pp\s*\*\s*|paypal\s*\*\s*|"
    r"in\s*\*\s*)+", re.I)
_NOISE_PATTERNS = [
    re.compile(r"\b(x{2,}|\*{2,})\d{2,}\b", re.I),        # masked card numbers
    re.compile(r"#\s*\d+"),                               # store numbers
    re.compile(r"\b\d{2}/\d{2}(/\d{2,4})?\b"),            # embedded dates
    re.compile(r"\b[a-z]*\d[a-z\d]{5,}\b", re.I),         # reference / auth codes
    re.compile(r"\b\d{5,}\b"),                            # long numbers
    re.compile(r"\s+[A-Z]{2}\s*$"),                       # trailing state code
]


@dataclass
class Transaction:
    date: str                     # ISO YYYY-MM-DD
    description: str              # as the bank wrote it
    amount: float                 # signed: < 0 money out, > 0 money in
    merchant: str = ""            # cleaned, human-friendly
    bank_category: str = ""
    category: str = UNCATEGORIZED
    category_source: str = ""     # rule | history | bank | keyword | none
    duplicate: bool = False
    row: int = 0                  # 1-based line in the source file

    @property
    def kind(self) -> str:
        return "expense" if self.amount < 0 else "income"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind
        return d


@dataclass
class ParseResult:
    transactions: List[Transaction] = field(default_factory=list)
    columns: Dict[str, str] = field(default_factory=dict)   # role -> header text
    date_format: str = ""
    ambiguous_dates: bool = False   # both M/D and D/M parse every row
    sign_guessed: bool = False      # every amount had the same sign; we assumed card-style
    skipped_rows: List[int] = field(default_factory=list)
    currency: str = ""              # from a currency column, if every row agreed


# A realistic checking-account export for the "try it" button and the demo app.
# Kept in code, not a .csv file, because *.csv is gitignored in this repo.
SAMPLE_STATEMENT = b"""Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
CREDIT,10/01/2026,"ACME CORP PAYROLL PPD ID: 9876543210",3200.00,ACH_CREDIT,4820.11,,
DEBIT,10/01/2026,"RENT PAYMENT OAK APARTMENTS",-1450.00,ACH_DEBIT,3370.11,,
DEBIT,10/02/2026,"SQ *BLUE BOTTLE COFFEE #12",-6.25,DEBIT_CARD,3363.86,,
DEBIT,10/03/2026,"WHOLEFDS MKT #10234",-84.17,DEBIT_CARD,3279.69,,
DEBIT,10/04/2026,"UBER *TRIP HELP.UBER.COM",-18.40,DEBIT_CARD,3261.29,,
DEBIT,10/05/2026,"NETFLIX.COM",-15.49,DEBIT_CARD,3245.80,,
DEBIT,10/06/2026,"SHELL OIL 57444",-41.02,DEBIT_CARD,3204.78,,
DEBIT,10/08/2026,"AMAZON.COM*AB12CD34E",-36.99,DEBIT_CARD,3167.79,,
DEBIT,10/09/2026,"COMCAST XFINITY",-79.99,ACH_DEBIT,3087.80,,
DEBIT,10/11/2026,"UBER EATS HELP.UBER.COM",-27.80,DEBIT_CARD,3060.00,,
DEBIT,10/12/2026,"TRADER JOE S #123",-52.64,DEBIT_CARD,3007.36,,
DEBIT,10/14/2026,"CVS/PHARMACY #0412",-23.15,DEBIT_CARD,2984.21,,
DEBIT,10/15/2026,"SPOTIFY USA",-11.99,DEBIT_CARD,2972.22,,
CREDIT,10/15/2026,"ACME CORP PAYROLL PPD ID: 9876543210",3200.00,ACH_CREDIT,6172.22,,
DEBIT,10/17/2026,"PLANET FITNESS",-24.99,ACH_DEBIT,6147.23,,
DEBIT,10/19/2026,"CHIPOTLE 2231",-14.85,DEBIT_CARD,6132.38,,
DEBIT,10/21/2026,"ZELLE TO J SMITH",-60.00,ACH_DEBIT,6072.38,,
DEBIT,10/24/2026,"KRISPY KORNER LLC",-9.50,DEBIT_CARD,6062.88,,
CREDIT,10/28/2026,"INTEREST PAYMENT",1.12,ACH_CREDIT,6064.00,,
"""


class StatementError(ValueError):
    """The file could not be understood as a bank statement."""


# ── Low-level helpers ────────────────────────────────────────────────────────
def _norm_header(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _decode(source: Any) -> str:
    """Accept a path, bytes, str, or file-like (incl. Streamlit's UploadedFile)."""
    if hasattr(source, "getvalue"):
        raw = source.getvalue()
    elif hasattr(source, "read"):
        raw = source.read()
    elif isinstance(source, (bytes, bytearray)):
        raw = bytes(source)
    elif isinstance(source, str) and "\n" not in source and len(source) < 1024:
        with open(source, "rb") as fh:
            raw = fh.read()
    else:
        raw = source
    if isinstance(raw, str):
        return raw.lstrip("﻿")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise StatementError("Could not decode the file as text.")


def read_rows(source: Any) -> List[List[str]]:
    text = _decode(source)
    if not text.strip():
        raise StatementError("The file is empty.")
    sample = "\n".join(text.splitlines()[:40])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ","
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), delimiter=delim)]


def _role_for(header: str) -> Optional[Tuple[str, Tuple[int, int]]]:
    """(role, rank) for a header cell; lower rank = better fit for that role."""
    h = _norm_header(header)
    if not h or any(b == h or h.startswith(b) for b in HEADER_BLOCKLIST):
        return None
    for role, aliases in HEADER_ALIASES.items():
        if h in aliases:
            return role, (0, aliases.index(h))
    for role, aliases in HEADER_ALIASES.items():
        for n, a in enumerate(aliases):
            if len(a) > 3 and a in h:
                return role, (1, n)
    return None


def detect_columns(header: List[str]) -> Dict[str, int]:
    """Map each role to its best column.

    Ranked, not first-come: a Chase export has "Details" (DEBIT/CREDIT) before
    "Description", and "Description" must win.
    """
    best: Dict[str, Tuple[Tuple[int, int], int]] = {}
    for i, cell in enumerate(header):
        hit = _role_for(cell)
        if hit:
            role, rank = hit
            if role not in best or rank < best[role][0]:
                best[role] = (rank, i)
    return {role: i for role, (_, i) in best.items()}


def find_header(rows: List[List[str]], scan: int = 30) -> Tuple[int, Dict[str, int]]:
    """Banks often put account details above the real header row; skip them."""
    for idx, row in enumerate(rows[:scan]):
        roles = detect_columns(row)
        if "date" in roles and ("amount" in roles or "debit" in roles or "credit" in roles):
            return idx, roles
    raise StatementError(
        "Couldn't find a header row with a date column and an amount "
        "(or debit/credit) column in the first %d lines." % scan)


def parse_amount(value: Any) -> Optional[float]:
    """'$1,234.56' '(12.00)' '12.00-' '1.234,56' '€ 9,99' '45.10 CR' -> float."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in ("-", "--"):
        return None
    neg = False
    upper = s.upper()
    if upper.endswith(("DR", "CR")):
        neg = upper.endswith("DR")
        s = s[:-2].strip()
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("-"):
        neg, s = not neg, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):          # 1.234,56  (European)
            s = s.replace(".", "").replace(",", ".")
        else:                                    # 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else s.replace(",", "")
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


def _clean_date_text(s: str) -> str:
    s = s.strip()
    # Drop a time component: "2024-01-05 13:22:00", "2024-01-05T13:22:00Z"
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ]", s)
    if m:
        return m.group(1)
    m = re.match(r"^(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s+\d", s)
    if m:
        return m.group(1)
    return s


def _hits(fmt: str, values: List[str]) -> int:
    n = 0
    for v in values:
        try:
            datetime.strptime(v, fmt)
            n += 1
        except ValueError:
            pass
    return n


def detect_date_format(values: Iterable[str], dayfirst: Optional[bool] = None) -> Tuple[str, bool]:
    """Choose ONE format for the whole column so 03/04 is read consistently.

    Footer cells ("Total", "Pending") are ignored; a format must read at least
    80% of the remaining values. Returns (format, ambiguous). ``ambiguous``
    means month-first and day-first read the column equally well - the caller
    should let the user decide.
    """
    vals = [_clean_date_text(v) for v in values if v and re.search(r"\d", v)]
    if not vals:
        raise StatementError("The date column is empty.")
    need = max(1, int(len(vals) * 0.8 + 0.999))

    def best(fmts):
        scored = [(_hits(f, vals), -i, f) for i, f in enumerate(fmts)]
        n, _, f = max(scored)
        return (f, n) if n >= need else (None, 0)

    f, _ = best(DATE_FORMATS_UNAMBIGUOUS)
    if f:
        return f, False
    mdy, n_mdy = best(DATE_FORMATS_MDY)
    dmy, n_dmy = best(DATE_FORMATS_DMY)
    if mdy and dmy:
        if n_mdy != n_dmy:
            return (mdy if n_mdy > n_dmy else dmy), False
        return (dmy if dayfirst else mdy), dayfirst is None
    if mdy or dmy:
        return (mdy or dmy), False
    raise StatementError(f"Unrecognised date format (e.g. {vals[0]!r}).")


def clean_merchant(description: str) -> str:
    """'SQ *BLUE BOTTLE COFFEE #123 OAKLAND CA' -> 'Blue Bottle Coffee Oakland'."""
    s = str(description or "").strip()
    s = _NOISE_PREFIXES.sub("", s)
    for pat in _NOISE_PATTERNS:
        s = pat.sub(" ", s)
    s = re.sub(r"[*_]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -.,")
    if not s:
        s = str(description or "").strip()
    return s.title() if s.isupper() or s.islower() else s


def merchant_key(description: str) -> str:
    """Stable key for matching the same merchant across statements."""
    words = re.sub(r"[^a-z ]", " ", clean_merchant(description).lower()).split()
    return " ".join(words[:3])


def _match_text(description: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", str(description).lower()).strip() + " "


def _keyword_index(rules: Dict[str, Iterable[str]]) -> List[Tuple[str, str]]:
    pairs = [(kw.lower(), cat) for cat, kws in rules.items() for kw in kws]
    return sorted(pairs, key=lambda p: -len(p[0]))


_EXPENSE_INDEX = _keyword_index(DEFAULT_RULES)
_INCOME_INDEX = _keyword_index(DEFAULT_INCOME_RULES)


def keyword_category(description: str, amount: float = -1.0) -> Optional[str]:
    text = _match_text(description)
    index = _EXPENSE_INDEX if amount < 0 else _INCOME_INDEX
    for kw, cat in index:
        if f" {_match_text(kw).strip()} " in text:
            return cat
    return None


# ── Categorizer ──────────────────────────────────────────────────────────────
class Categorizer:
    """user rules > your history > bank's own category > built-in keywords.

    History is the important one commercially: every time a user re-tags an
    imported transaction, the next import of that merchant follows suit, with
    no AI call and nothing leaving the machine.
    """

    def __init__(self, user_rules: Optional[Dict[str, str]] = None,
                 history: Optional[Iterable[Tuple[str, str]]] = None) -> None:
        # user_rules: {"substring": "Category"}; longest pattern wins.
        self.user_rules = sorted(((k.lower(), v) for k, v in (user_rules or {}).items() if k),
                                 key=lambda p: -len(p[0]))
        votes: Dict[str, Counter] = defaultdict(Counter)
        for desc, cat in history or ():
            if cat and cat != UNCATEGORIZED:
                k = merchant_key(desc)
                if k:
                    votes[k][cat] += 1
        self.history = {k: c.most_common(1)[0][0] for k, c in votes.items()}

    def categorize(self, description: str, amount: float,
                   bank_category: str = "") -> Tuple[str, str]:
        low = str(description).lower()
        for pattern, cat in self.user_rules:
            if pattern in low:
                return cat, "rule"
        hist = self.history.get(merchant_key(description))
        if hist:
            return hist, "history"
        if bank_category and bank_category.strip():
            return bank_category.strip().title(), "bank"
        kw = keyword_category(description, amount)
        if kw:
            return kw, "keyword"
        return UNCATEGORIZED, "none"


# ── Parse ────────────────────────────────────────────────────────────────────
def _cell(row: List[str], idx: Optional[int]) -> str:
    return row[idx] if idx is not None and idx < len(row) else ""


def parse_statement(source: Any, *, dayfirst: Optional[bool] = None,
                    outflow_positive: Optional[bool] = None) -> ParseResult:
    """Turn a bank CSV into signed, dated Transactions (not yet categorized).

    ``outflow_positive``: True for exports where purchases are positive numbers
    (most credit-card statements). None = auto-detect; if every amount has the
    clear majority are positive we assume card-style and set ``sign_guessed`` so
    the UI can offer a flip.
    """
    rows = read_rows(source)
    hdr_idx, cols = find_header(rows)
    header = rows[hdr_idx]
    body = [(hdr_idx + 2 + i, r) for i, r in enumerate(rows[hdr_idx + 1:])
            if any(c.strip() for c in r)]

    res = ParseResult(columns={role: header[i] for role, i in cols.items()})
    date_i = cols["date"]
    date_vals = [_cell(r, date_i) for _, r in body]
    res.date_format, res.ambiguous_dates = detect_date_format(
        [v for v in date_vals if v], dayfirst)

    desc_i = cols.get("description")
    currencies = set()
    raw: List[Transaction] = []
    for line, r in body:
        d = _clean_date_text(_cell(r, date_i))
        try:
            iso = datetime.strptime(d, res.date_format).strftime("%Y-%m-%d")
        except ValueError:
            res.skipped_rows.append(line)       # footers, totals, "Pending" etc.
            continue
        if "amount" in cols:
            amt = parse_amount(_cell(r, cols["amount"]))
            t = _cell(r, cols.get("type")).strip().lower()
            if amt is not None and t:
                if t in ("debit", "dr", "d", "withdrawal", "sale", "purchase", "payment out"):
                    amt = -abs(amt)
                elif t in ("credit", "cr", "c", "deposit", "refund", "return"):
                    amt = abs(amt)
        else:
            out = parse_amount(_cell(r, cols.get("debit")))
            inn = parse_amount(_cell(r, cols.get("credit")))
            if out is None and inn is None:
                amt = None
            else:
                amt = abs(inn or 0.0) - abs(out or 0.0)
        if amt is None or amt == 0:
            res.skipped_rows.append(line)
            continue
        desc = _cell(r, desc_i) if desc_i is not None else ""
        if not desc:
            # Some banks spread the payee across unnamed columns; use the widest text cell.
            texts = [c for j, c in enumerate(r) if j not in cols.values() and parse_amount(c) is None]
            desc = max(texts, key=len) if texts else "Unknown"
        if "currency" in cols:
            currencies.add(_cell(r, cols["currency"]).strip().lower())
        raw.append(Transaction(date=iso, description=desc, amount=round(amt, 2),
                               merchant=clean_merchant(desc),
                               bank_category=_cell(r, cols.get("category")), row=line))

    if not raw:
        raise StatementError("No transactions found under the header row.")

    single_amount_col = "amount" in cols and "type" not in cols
    if outflow_positive is None and single_amount_col and len(raw) >= 3:
        # Bank accounts have more money-out rows than money-in; card statements
        # list purchases as positives. A clear positive majority means card-style.
        positive = sum(1 for t in raw if t.amount > 0) / len(raw)
        if positive > 0.6:
            outflow_positive, res.sign_guessed = True, True
    if outflow_positive and single_amount_col:
        for t in raw:
            t.amount = -t.amount

    currencies.discard("")
    if len(currencies) == 1:
        res.currency = currencies.pop()
    res.transactions = raw
    return res


# ── Duplicates ───────────────────────────────────────────────────────────────
def fingerprint(date: str, amount: float, description: str) -> Tuple[str, float, str]:
    return (str(date)[:10], round(abs(float(amount)), 2), merchant_key(description))


def mark_duplicates(transactions: List[Transaction],
                    existing: Iterable[Tuple[str, float, str]]) -> int:
    """Flag transactions already present in the user's data.

    Count-aware: two identical $4.50 coffees on the same day are both kept the
    first time, and both flagged when the same file is imported again.
    """
    pool = Counter(existing)
    n = 0
    for t in transactions:
        fp = fingerprint(t.date, t.amount, t.description)
        if pool[fp] > 0:
            pool[fp] -= 1
            t.duplicate = True
            n += 1
    return n


def _f(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def existing_fingerprints(data: Dict[str, Any]) -> List[Tuple[str, float, str]]:
    """Fingerprints of what is already stored, from the finance blob.

    Imported rows keep the bank's original text in ``bank_description`` so a
    re-import still matches after the user renames the item.
    """
    fps = []
    for e in data.get("expenses") or []:
        fps.append(fingerprint(e.get("date", ""), _f(e.get("price")),
                               e.get("bank_description") or e.get("purchased", "")))
    for i in data.get("income") or []:
        fps.append(fingerprint(i.get("date", ""), _f(i.get("amount")),
                               i.get("bank_description") or i.get("source", "")))
    return fps


def history_pairs(data: Dict[str, Any]) -> List[Tuple[str, str]]:
    """(description, category) pairs the user has already settled on."""
    pairs = []
    for e in data.get("expenses") or []:
        tag = e.get("tags")
        if tag:
            pairs.append((e.get("purchased", ""), tag))
            if e.get("bank_description"):
                pairs.append((e["bank_description"], tag))
    return pairs
