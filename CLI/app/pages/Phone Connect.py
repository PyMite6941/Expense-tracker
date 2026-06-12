import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from CLI.app.streamlit_setup import init_st

init_st()

st.set_page_config(page_title='Phone Connect', page_icon='📱')
st.title('📱 Phone Connect')
st.caption('Control your expense tracker from Telegram or Discord — Pro & Max feature.')

# ── License gate ───────────────────────────────────────────────────────────────

_features = st.session_state.get('pro_features', [])
if 'bot_connect' not in _features:
    st.warning(
        '**Phone Connect requires a Pro or Max license.**\n\n'
        'Activate your license key on the ⭐ Pro Features page to unlock this.'
    )
    st.stop()

# ── Config persistence (stored in .bot_config.json, gitignored) ────────────────

_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '.bot_config.json'
)
_CONFIG_PATH = os.path.abspath(_CONFIG_PATH)


def _load_cfg() -> dict:
    try:
        if os.path.exists(_CONFIG_PATH):
            return json.loads(open(_CONFIG_PATH).read())
    except Exception:
        pass
    return {}


def _save_cfg(cfg: dict) -> None:
    with open(_CONFIG_PATH, 'w') as fh:
        json.dump(cfg, fh, indent=2)


cfg = _load_cfg()

# ── Tabs: Telegram | Discord ───────────────────────────────────────────────────

tab_tg, tab_dc, tab_cmds = st.tabs(['Telegram', 'Discord', 'Bot Commands'])

# ─── Telegram tab ──────────────────────────────────────────────────────────────

with tab_tg:
    st.subheader('Telegram Bot Setup')

    with st.expander('How to create a Telegram bot (one-time setup)', expanded=False):
        st.markdown(
            """
1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts.
3. Copy the **HTTP API token** BotFather gives you.
4. Paste it below, then click **Save**.
5. Run the bot on your computer (see command below).
6. Search for your new bot in Telegram and send **/start**.
            """
        )

    tg_token = st.text_input(
        'Telegram Bot Token',
        value=cfg.get('telegram_token', ''),
        type='password',
        placeholder='110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw',
    )

    if st.button('Save Telegram Token', type='primary'):
        cfg['telegram_token'] = tg_token
        _save_cfg(cfg)
        st.success('Token saved.')

    if cfg.get('telegram_token'):
        st.success('Telegram token is configured.', icon='✅')

    st.divider()
    st.markdown('**Start the bot on your computer:**')
    st.code('python backend/phone_connect.py --platform telegram', language='bash')
    st.caption(
        'Keep this terminal open while you want to use the bot. '
        'You can also set the `TELEGRAM_BOT_TOKEN` environment variable instead of saving the token here.'
    )

# ─── Discord tab ───────────────────────────────────────────────────────────────

with tab_dc:
    st.subheader('Discord Bot Setup')

    with st.expander('How to create a Discord bot (one-time setup)', expanded=False):
        st.markdown(
            """
1. Go to the **Discord Developer Portal** (discord.com/developers/applications).
2. Click **New Application**, give it a name.
3. Open the **Bot** tab and click **Add Bot**.
4. Under **Token**, click **Reset Token** and copy it.
5. Under **Privileged Gateway Intents**, enable **Message Content Intent**.
6. Paste the token below and click **Save**.
7. Go to **OAuth2 → URL Generator**, select `bot` scope and `Send Messages` + `Read Message History` permissions.
8. Open the generated URL in a browser and invite the bot to your server.
9. Run the bot on your computer (see command below).
            """
        )

    dc_token = st.text_input(
        'Discord Bot Token',
        value=cfg.get('discord_token', ''),
        type='password',
        placeholder='YOUR_DISCORD_BOT_TOKEN_HERE',
    )

    if st.button('Save Discord Token', type='primary'):
        cfg['discord_token'] = dc_token
        _save_cfg(cfg)
        st.success('Token saved.')

    if cfg.get('discord_token'):
        st.success('Discord token is configured.', icon='✅')

    st.divider()
    st.markdown('**Start the bot on your computer:**')
    st.code('python backend/phone_connect.py --platform discord', language='bash')
    st.caption(
        'Keep this terminal open while you want to use the bot. '
        'Use `!<command>` in Discord (e.g. `!summary`, `!help`).'
    )

# ─── Commands reference tab ────────────────────────────────────────────────────

with tab_cmds:
    st.subheader('Available Bot Commands')
    st.markdown(
        """
| Command | Telegram | Discord | Description |
|---------|----------|---------|-------------|
| Start / Welcome | `/start` | `!start` | Introduction message |
| Help | `/help` | `!help` | List all commands |
| Summary | `/summary` | `!summary` | Total income, expenses & balance with recent 5 expenses |
| Balance | `/balance` | `!balance` | This month's income vs expenses |
| Budget | `/budget` | `!budget` | Budget usage by category this month |
| Add expense | `/add 12.50 Food Lunch` | `!add 12.50 Food Lunch` | Log a new expense |
        """
    )

    st.info(
        'The bot reads from (and writes to) the same **data.json** file used by '
        'the desktop app, so changes are reflected everywhere instantly.',
        icon='ℹ️',
    )

    st.divider()
    st.markdown('**Add expense syntax:**')
    st.code('/add <amount> <category> <description...>', language='text')
    st.markdown('Examples:')
    st.code(
        '/add 45.00 Food Dinner with friends\n'
        '/add 9.99 Subscriptions Netflix\n'
        '/add 120 Travel Uber to airport',
        language='text',
    )
