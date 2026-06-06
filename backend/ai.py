import os
import json
import requests

_PROVIDERS = {
    'groq': {
        'base_url': 'https://api.groq.com/openai/v1',
        'default_model': 'llama-3.1-8b-instant',
    },
    'openrouter': {
        'base_url': 'https://openrouter.ai/api/v1',
        'default_model': 'meta-llama/llama-3.1-8b-instruct:free',
    },
}

_CATEGORIES = ['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other']


def is_configured() -> bool:
    return bool(os.environ.get('AI_API_KEY', '').strip())


def _provider_config() -> tuple[str, str, str]:
    name = os.environ.get('AI_PROVIDER', 'groq').lower()
    cfg = _PROVIDERS.get(name, _PROVIDERS['groq'])
    key = os.environ.get('AI_API_KEY', '')
    model = os.environ.get('AI_MODEL', cfg['default_model'])
    return cfg['base_url'], key, model


def _chat(messages: list, max_tokens: int = 512, temperature: float = 0.3) -> str:
    base_url, api_key, model = _provider_config()
    resp = requests.post(
        f'{base_url}/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={'model': model, 'messages': messages, 'max_tokens': max_tokens, 'temperature': temperature},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()


def suggest_category(merchant: str, amount: float, categories: list = None) -> str:
    cats = categories or _CATEGORIES
    messages = [
        {
            'role': 'system',
            'content': (
                f'You are an expense categorizer. Given a merchant name and purchase amount, '
                f'respond with exactly one word from this list: {", ".join(cats)}. '
                'No punctuation, no explanation — just the single category name.'
            ),
        },
        {'role': 'user', 'content': f'Merchant: {merchant}\nAmount: {amount}'},
    ]
    raw = _chat(messages, max_tokens=10, temperature=0)
    for cat in cats:
        if cat.lower() in raw.lower():
            return cat
    return 'Other'


def recommend_budgets(expenses: list, income: list) -> dict:
    from datetime import date
    today = date.today()
    three_months_ago = f"{today.year}-{today.month - 3:02d}" if today.month > 3 else \
        f"{today.year - 1}-{today.month + 9:02d}"
    recent = [e for e in expenses if e.get('date', '') >= three_months_ago]

    from collections import defaultdict
    totals: dict = defaultdict(list)
    for e in recent:
        totals[e.get('tags', 'Other')].append(e.get('price', 0))
    avg_by_cat = {cat: sum(v) / max(1, len(v)) * len(set(e['date'][:7] for e in recent if e.get('tags') == cat))
                  for cat, v in totals.items()}

    monthly_income = sum(i.get('amount', 0) for i in income) / max(1, len(
        set(i['date'][:7] for i in income if i.get('date'))
    )) if income else 0

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a personal finance advisor. Given recent average monthly spending per category '
                'and the user\'s average monthly income, suggest realistic budget limits for each category. '
                'Respond with a JSON object: {"recommendations": [{"category": str, "suggested_limit": float, '
                '"reasoning": str}]}. Use numbers only, no markdown.'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Monthly income: {monthly_income:.2f}\n'
                f'Recent avg monthly spend by category:\n' +
                '\n'.join(f'  {cat}: {amt:.2f}' for cat, amt in sorted(avg_by_cat.items()))
            ),
        },
    ]
    raw = _chat(messages, max_tokens=400, temperature=0.2)
    try:
        import json as _json
        start = raw.find('{')
        end = raw.rfind('}') + 1
        return _json.loads(raw[start:end]) if start >= 0 else {'recommendations': []}
    except Exception:
        return {'recommendations': [], 'raw': raw}


def answer_query(question: str, financial_data: dict) -> str:
    summary = {
        'expenses': financial_data.get('expenses', [])[-100:],
        'income': financial_data.get('income', [])[-100:],
        'budget': financial_data.get('budget', []),
        'subscriptions': financial_data.get('subscriptions', []),
        'goals': financial_data.get('goals', []),
    }
    messages = [
        {
            'role': 'system',
            'content': (
                'You are a helpful financial assistant. Answer the user\'s question concisely '
                'using only the provided financial data. Format currency values to 2 decimal places. '
                'If data is insufficient to answer, say so clearly.'
            ),
        },
        {
            'role': 'user',
            'content': f'Financial data:\n{json.dumps(summary, indent=2)}\n\nQuestion: {question}',
        },
    ]
    return _chat(messages, max_tokens=600, temperature=0.3)
