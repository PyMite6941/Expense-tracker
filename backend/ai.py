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
