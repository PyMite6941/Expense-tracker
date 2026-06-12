"""
Phone Connect Bot — access your expense tracker from Telegram or Discord.

Usage:
  python backend/phone_connect.py --platform telegram
  python backend/phone_connect.py --platform discord

Configure your bot token in configs.toml ([telegram] or [discord] section)
or via environment variables TELEGRAM_BOT_TOKEN / DISCORD_BOT_TOKEN.

Bot commands (same on both platforms):
  /start   — welcome message
  /help    — list commands
  /summary — spending summary + recent expenses
  /budget  — budget usage this month
  /add <amount> <category> <description> — log a new expense
  /balance — quick income vs expense balance
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

# Resolve project root so the bot can import CLI modules regardless of cwd.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

from CLI.core.core_stuff import ExpenseTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Config helpers ─────────────────────────────────────────────────────────────

def _load_toml_config() -> dict:
    path = _ROOT / "configs.toml"
    if path.exists() and tomllib is not None:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    return {}


def _load_bot_config() -> dict:
    """Load runtime config saved by the Streamlit UI."""
    path = _ROOT / ".bot_config.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def _get_token(platform: str) -> str:
    env_key = f"{platform.upper()}_BOT_TOKEN"
    token = os.getenv(env_key, "")
    if token:
        return token
    bot_cfg = _load_bot_config()
    token = bot_cfg.get(f"{platform}_token", "")
    if token:
        return token
    toml_cfg = _load_toml_config()
    token = toml_cfg.get(platform, {}).get("bot_token", "")
    return token


def _get_data_file() -> str:
    toml_cfg = _load_toml_config()
    rel = toml_cfg.get("app", {}).get("data_file", "data.json")
    # Always resolve relative to project root so the correct data.json is used
    # regardless of the working directory when the bot is started.
    if not os.path.isabs(rel):
        return str(_ROOT / rel)
    return rel


# ── Shared command logic ───────────────────────────────────────────────────────

def _summary_text(tracker: ExpenseTracker) -> str:
    data = tracker.open_file()["data"]
    expenses = data.get("expenses", [])
    income = data.get("income", [])

    total_exp = sum(e.get("price", 0) for e in expenses)
    total_inc = sum(i.get("amount", 0) for i in income)
    balance = total_inc - total_exp

    recent = sorted(expenses, key=lambda x: x.get("date", ""), reverse=True)[:5]
    lines = [
        f"  • {e.get('purchased','?')} — {e.get('price',0):.2f} {e.get('currency','').upper()} [{e.get('tags','?')}]"
        for e in recent
    ]
    recent_str = "\n".join(lines) if lines else "  (no expenses yet)"

    return (
        f"📊 Expense Summary\n"
        f"💸 Total Expenses : {total_exp:,.2f}\n"
        f"💰 Total Income   : {total_inc:,.2f}\n"
        f"📈 Balance        : {balance:+,.2f}\n\n"
        f"📋 Recent 5 expenses:\n{recent_str}"
    )


def _balance_text(tracker: ExpenseTracker) -> str:
    data = tracker.open_file()["data"]
    expenses = data.get("expenses", [])
    income = data.get("income", [])
    current_month = datetime.now().strftime("%Y-%m")

    month_exp = sum(e.get("price", 0) for e in expenses if e.get("date", "").startswith(current_month))
    month_inc = sum(i.get("amount", 0) for i in income if i.get("date", "").startswith(current_month))

    return (
        f"💳 This Month ({current_month})\n"
        f"Income  : {month_inc:,.2f}\n"
        f"Expenses: {month_exp:,.2f}\n"
        f"Net     : {month_inc - month_exp:+,.2f}"
    )


def _budget_text(tracker: ExpenseTracker) -> str:
    data = tracker.open_file()["data"]
    budgets = data.get("budget", [])
    expenses = data.get("expenses", [])

    if not budgets:
        return "ℹ️ No budgets set. Add budgets in the app first."

    current_month = datetime.now().strftime("%Y-%m")
    month_exp = [e for e in expenses if e.get("date", "").startswith(current_month)]
    cat_totals: dict = {}
    for e in month_exp:
        cat = e.get("tags", "Other")
        cat_totals[cat] = cat_totals.get(cat, 0) + e.get("price", 0)

    lines = [f"💼 Budget Status — {current_month}"]
    for b in budgets:
        cat = b.get("category", "?")
        limit = float(b.get("limit", b.get("amount", 0)))
        spent = cat_totals.get(cat, 0)
        pct = (spent / limit * 100) if limit > 0 else 0
        bar = "🟩" if pct < 75 else "🟨" if pct < 100 else "🟥"
        lines.append(f"{bar} {cat}: {spent:.2f} / {limit:.2f} ({pct:.0f}%)")

    return "\n".join(lines)


def _add_expense_text(tracker: ExpenseTracker, amount: float, category: str, description: str) -> str:
    result = tracker.add_expenses(
        price=amount,
        purchased=description,
        tags=category,
        currency="usd",
        date=datetime.now().strftime("%Y-%m-%d"),
        notes="Added via bot",
    )
    if result.get("success"):
        return f"✅ Expense added: {description} — {amount:.2f} [{category}]"
    return f"❌ Could not add expense: {result.get('message','unknown error')}"


HELP_TEXT = (
    "🤖 Expense Tracker Bot Commands\n\n"
    "/summary — spending overview & recent expenses\n"
    "/balance — this month's income vs expenses\n"
    "/budget  — budget usage by category\n"
    "/add <amount> <category> <description>\n"
    "  e.g. /add 12.50 Food Lunch at cafe\n"
    "/help    — show this message"
)


# ── Telegram bot ───────────────────────────────────────────────────────────────

def run_telegram(token: str, data_file: str) -> None:
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
    except ImportError:
        log.error("python-telegram-bot is not installed. Run: pip install 'python-telegram-bot>=20.0'")
        sys.exit(1)

    tracker = ExpenseTracker(filename=data_file)

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "👋 Welcome to your Expense Tracker Bot!\nUse /help to see available commands."
        )

    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(HELP_TEXT)

    async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(_summary_text(tracker))

    async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(_balance_text(tracker))

    async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(_budget_text(tracker))

    async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args or []
        if len(args) < 3:
            await update.message.reply_text(
                "Usage: /add <amount> <category> <description>\n"
                "Example: /add 12.50 Food Lunch at cafe"
            )
            return
        try:
            amount = float(args[0])
        except ValueError:
            await update.message.reply_text("❌ Amount must be a number (e.g. 12.50)")
            return
        category = args[1]
        description = " ".join(args[2:])
        await update.message.reply_text(_add_expense_text(tracker, amount, category, description))

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("budget",  cmd_budget))
    app.add_handler(CommandHandler("add",     cmd_add))

    log.info("Telegram bot running — send /start to your bot on Telegram.")
    app.run_polling()


# ── Discord bot ────────────────────────────────────────────────────────────────

def run_discord(token: str, data_file: str) -> None:
    try:
        import discord
        from discord.ext import commands
    except ImportError:
        log.error("discord.py is not installed. Run: pip install 'discord.py>=2.0'")
        sys.exit(1)

    tracker = ExpenseTracker(filename=data_file)

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

    @bot.event
    async def on_ready() -> None:
        log.info(f"Discord bot ready as {bot.user}")

    @bot.command(name="start")
    async def cmd_start(ctx: commands.Context) -> None:
        await ctx.send("👋 Welcome to your Expense Tracker Bot!\nUse `!help` to see available commands.")

    @bot.command(name="help")
    async def cmd_help(ctx: commands.Context) -> None:
        await ctx.send(HELP_TEXT.replace("/", "!"))

    @bot.command(name="summary")
    async def cmd_summary(ctx: commands.Context) -> None:
        await ctx.send(_summary_text(tracker))

    @bot.command(name="balance")
    async def cmd_balance(ctx: commands.Context) -> None:
        await ctx.send(_balance_text(tracker))

    @bot.command(name="budget")
    async def cmd_budget(ctx: commands.Context) -> None:
        await ctx.send(_budget_text(tracker))

    @bot.command(name="add")
    async def cmd_add(ctx: commands.Context, *args: str) -> None:
        if len(args) < 3:
            await ctx.send(
                "Usage: `!add <amount> <category> <description>`\n"
                "Example: `!add 12.50 Food Lunch at cafe`"
            )
            return
        try:
            amount = float(args[0])
        except ValueError:
            await ctx.send("❌ Amount must be a number (e.g. 12.50)")
            return
        category = args[1]
        description = " ".join(args[2:])
        await ctx.send(_add_expense_text(tracker, amount, category, description))

    log.info("Discord bot starting…")
    bot.run(token)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Expense Tracker Phone Connect Bot")
    parser.add_argument("--platform", choices=["telegram", "discord"], required=True,
                        help="Which bot platform to run")
    parser.add_argument("--data-file", default=None,
                        help="Path to data.json (defaults to value in configs.toml)")
    ns = parser.parse_args()

    data_file = ns.data_file or _get_data_file()
    token = _get_token(ns.platform)

    if not token:
        log.error(
            f"No {ns.platform} bot token found.\n"
            f"  Option 1: Set the {ns.platform.upper()}_BOT_TOKEN environment variable.\n"
            f"  Option 2: Enter the token on the Phone Connect page in the Web UI.\n"
            f"  Option 3: Add it to configs.toml under [{ns.platform}] bot_token."
        )
        sys.exit(1)

    if ns.platform == "telegram":
        run_telegram(token, data_file)
    else:
        run_discord(token, data_file)


if __name__ == "__main__":
    main()
