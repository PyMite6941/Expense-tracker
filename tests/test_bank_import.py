"""Bank statement parsing, categorization and de-duplication."""
import pytest

from CLI.core import bank_import as bi
from CLI.core.bank_import import (Categorizer, StatementError, clean_merchant,
                                  merchant_key, parse_amount, parse_statement,
                                  detect_date_format)

CHASE_CHECKING = b"""Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,01/15/2026,"STARBUCKS STORE 12345 SEATTLE WA",-5.75,DEBIT_CARD,1994.25,,
DEBIT,01/16/2026,"WHOLEFDS MKT #10234",-82.10,DEBIT_CARD,1912.15,,
CREDIT,01/17/2026,"ACME CORP PAYROLL PPD ID: 9876543210",2500.00,ACH_CREDIT,4412.15,,
DEBIT,01/18/2026,"UBER EATS HELP.UBER.COM",-23.40,DEBIT_CARD,4388.75,,
DEBIT,01/19/2026,"UBER *TRIP HELP.UBER.COM",-14.00,DEBIT_CARD,4374.75,,
"""

# Amex: purchases positive, payments negative, no type column.
AMEX = b"""Date,Description,Amount
01/03/2026,NETFLIX.COM,15.49
01/05/2026,AMAZON.COM*AB12CD34E,42.99
01/09/2026,SHELL OIL 57444,38.20
01/20/2026,AUTOPAY PAYMENT - THANK YOU,-500.00
01/22/2026,TRADER JOE S #123,61.07
"""

# UK bank: account info preamble, dd/mm/yyyy, separate Money Out / Money In.
UK = b"""Account Name:,Current Account
Sort Code:,12-34-56

Date,Description,Money Out,Money In,Balance
03/01/2026,TESCO STORES 2041,"\xa312.40",,"\xa31,000.00"
14/01/2026,SALARY ACME LTD,,"\xa32,100.00","\xa33,087.60"
20/01/2026,TFL TRAVEL CH,5.60,,"\xa33,082.00"
Total,,,,
"""

# European formatting with semicolons.
EU = "Buchungstag;Verwendungszweck;Betrag\n05.01.2026;REWE Markt;-1.234,56\n06.01.2026;Gehalt;2.000,00\n".encode("utf-8")


class TestAmounts:
    @pytest.mark.parametrize("raw,expected", [
        ("12.50", 12.5), ("-12.50", -12.5), ("$1,234.56", 1234.56), ("(45.00)", -45.0),
        ("45.00-", -45.0), ("1.234,56", 1234.56), ("9,99", 9.99), ("€ 9,99", 9.99),
        ("45.10 DR", -45.1), ("45.10 CR", 45.1), ("+3", 3.0), ("1,000", 1000.0),
        ("", None), ("-", None), ("abc", None),
    ])
    def test_parse_amount(self, raw, expected):
        assert parse_amount(raw) == expected


class TestDates:
    def test_iso_unambiguous(self):
        assert detect_date_format(["2026-01-05", "2026-01-31"]) == ("%Y-%m-%d", False)

    def test_day_first_detected_from_values(self):
        assert detect_date_format(["03/01/2026", "14/01/2026"])[0] == "%d/%m/%Y"

    def test_ambiguous_defaults_month_first_and_flags(self):
        fmt, ambiguous = detect_date_format(["03/04/2026", "05/06/2026"])
        assert fmt == "%m/%d/%Y" and ambiguous

    def test_ambiguous_respects_dayfirst(self):
        assert detect_date_format(["03/04/2026"], dayfirst=True) == ("%d/%m/%Y", False)

    def test_time_component_ignored(self):
        assert detect_date_format(["2026-01-05 13:22:00", "2026-01-06T09:00:00Z"])[0] == "%Y-%m-%d"

    def test_garbage_raises(self):
        with pytest.raises(StatementError):
            detect_date_format(["yesterday"])


class TestParse:
    def test_chase_prefers_description_over_details(self):
        res = parse_statement(CHASE_CHECKING)
        assert res.columns["description"] == "Description"
        assert [t.amount for t in res.transactions] == [-5.75, -82.10, 2500.0, -23.40, -14.0]
        assert res.transactions[0].date == "2026-01-15"
        assert not res.sign_guessed

    def test_amex_card_style_signs_are_flipped(self):
        res = parse_statement(AMEX)
        assert res.sign_guessed
        amounts = [t.amount for t in res.transactions]
        assert amounts[0] == -15.49 and amounts[3] == 500.0

    def test_explicit_sign_overrides_guess(self):
        res = parse_statement(AMEX, outflow_positive=False)
        assert not res.sign_guessed and res.transactions[0].amount == 15.49

    def test_uk_preamble_debit_credit_columns_and_footer(self):
        res = parse_statement(UK)
        t = res.transactions
        assert [x.date for x in t] == ["2026-01-03", "2026-01-14", "2026-01-20"]
        assert [x.amount for x in t] == [-12.40, 2100.0, -5.60]
        assert res.skipped_rows  # the "Total" footer

    def test_european_semicolon_file(self):
        res = parse_statement(EU)
        assert [t.amount for t in res.transactions] == [-1234.56, 2000.0]
        assert res.transactions[0].date == "2026-01-05"

    def test_accepts_path_and_filelike(self, tmp_path):
        import io
        p = tmp_path / "s.csv"
        p.write_bytes(AMEX)
        assert len(parse_statement(str(p)).transactions) == 5
        assert len(parse_statement(io.BytesIO(AMEX)).transactions) == 5

    def test_no_header_raises(self):
        with pytest.raises(StatementError):
            parse_statement(b"foo,bar\n1,2\n")

    def test_empty_raises(self):
        with pytest.raises(StatementError):
            parse_statement(b"")


class TestMerchants:
    @pytest.mark.parametrize("raw,expected", [
        ("SQ *BLUE BOTTLE COFFEE", "Blue Bottle Coffee"),
        ("STARBUCKS STORE 12345 SEATTLE WA", "Starbucks Store Seattle"),
        ("TRADER JOE S #123", "Trader Joe S"),
        ("POS PURCHASE TARGET 00012345", "Target"),
    ])
    def test_clean(self, raw, expected):
        assert clean_merchant(raw) == expected

    def test_key_is_stable_after_cleaning(self):
        # Hosted mode stores only the cleaned name; dedupe must still match.
        for raw in ["STARBUCKS STORE 12345 SEATTLE WA", "AMAZON.COM*AB12CD34E",
                    "SQ *BLUE BOTTLE COFFEE #9", "UBER *TRIP HELP.UBER.COM"]:
            assert merchant_key(raw) == merchant_key(clean_merchant(raw))


class TestCategorize:
    def test_keywords_longest_wins(self):
        c = Categorizer()
        assert c.categorize("UBER EATS HELP.UBER.COM", -20)[0] == "Dining"
        assert c.categorize("UBER *TRIP", -14)[0] == "Transport"
        assert c.categorize("NETFLIX.COM", -15)[0] == "Subscriptions"
        assert c.categorize("AMAZON PRIME*1A2B3", -14)[0] == "Subscriptions"
        assert c.categorize("AMAZON.COM*AB12CD34E", -42)[0] == "Shopping"

    def test_income_uses_income_vocabulary(self):
        assert Categorizer().categorize("ACME CORP PAYROLL", 2500) == ("Salary", "keyword")

    def test_word_boundaries(self):
        # "bar" must not fire inside "barnes"
        assert Categorizer().categorize("BARNES ANDXYZ", -10)[0] != "Dining"

    def test_priority_rule_history_bank_keyword(self):
        c = Categorizer(user_rules={"starbucks": "Work coffee"},
                        history=[("BLUE BOTTLE COFFEE #1", "Treats")])
        assert c.categorize("STARBUCKS 123", -5) == ("Work coffee", "rule")
        assert c.categorize("SQ *BLUE BOTTLE COFFEE #77", -5) == ("Treats", "history")
        assert c.categorize("UNKNOWN SHOP", -5, bank_category="home improvement") == ("Home Improvement", "bank")
        assert c.categorize("UNKNOWN SHOP", -5) == ("Uncategorized", "none")

    def test_history_majority_vote(self):
        c = Categorizer(history=[("Joe's Diner", "Dining"), ("Joe's Diner", "Work"),
                                 ("Joe's Diner", "Work")])
        assert c.categorize("JOE'S DINER", -9)[0] == "Work"


class TestDuplicates:
    def test_count_aware(self):
        res = parse_statement(b"Date,Description,Amount,Type\n"
                              b"2026-01-02,COFFEE,4.50,debit\n2026-01-02,COFFEE,4.50,debit\n")
        existing = [bi.fingerprint("2026-01-02", 4.5, "Coffee")]
        assert bi.mark_duplicates(res.transactions, existing) == 1
        assert [t.duplicate for t in res.transactions] == [True, False]


def test_bank_abbreviations():
    assert Categorizer().categorize("WHOLEFDS MKT #10234", -82)[0] == "Groceries"
