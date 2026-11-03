// Bring-your-own-key AI. To keep the app cloud-free, there is NO backend: the
// user pastes their own Groq or OpenRouter key (stored only in localStorage) and
// the browser calls the provider directly. Financial data is sent to the chosen
// provider ONLY when the user runs an AI action — this is disclosed in the UI.

const KEY_LS = 'grid-expense-tracker/ai-key'
const PROVIDER_LS = 'grid-expense-tracker/ai-provider'

export const PROVIDERS = {
  groq: {
    label: 'Groq',
    url: 'https://api.groq.com/openai/v1/chat/completions',
    model: 'openai/gpt-oss-20b',
    keyHint: 'gsk_…  (console.groq.com/keys)',
  },
  openrouter: {
    label: 'OpenRouter',
    url: 'https://openrouter.ai/api/v1/chat/completions',
    model: 'meta-llama/llama-3.3-70b-instruct:free',
    keyHint: 'sk-or-…  (openrouter.ai/keys)',
  },
}

export function getAIConfig() {
  return {
    key: localStorage.getItem(KEY_LS) || '',
    provider: localStorage.getItem(PROVIDER_LS) || 'groq',
  }
}

export function setAIConfig({ key, provider }) {
  if (key !== undefined) localStorage.setItem(KEY_LS, key)
  if (provider !== undefined) localStorage.setItem(PROVIDER_LS, provider)
}

export function aiConfigured() {
  return !!getAIConfig().key
}

async function chat(messages, { maxTokens = 700 } = {}) {
  const { key, provider } = getAIConfig()
  if (!key) throw new Error('No API key set. Add one in the AI settings.')
  const p = PROVIDERS[provider] || PROVIDERS.groq
  const res = await fetch(p.url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
    body: JSON.stringify({ model: p.model, messages, temperature: 0.4, max_tokens: maxTokens }),
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`Provider error ${res.status}: ${txt.slice(0, 200)}`)
  }
  const json = await res.json()
  return json.choices?.[0]?.message?.content?.trim() || '(empty response)'
}

const compact = (data) => ({
  expenses: (data.expenses || []).slice(-60),
  income: (data.income || []).slice(-40),
  budget: data.budget || [],
  subscriptions: data.subscriptions || [],
  goals: data.goals || [],
})

export function recommendBudgets(data) {
  return chat([
    { role: 'system', content: 'You are a concise personal-finance budgeting assistant. Reply in short markdown.' },
    { role: 'user', content: `Based on this finance data, suggest realistic monthly budgets per category and one tip.\n\n${JSON.stringify(compact(data))}` },
  ])
}

export function askQuestion(data, question) {
  return chat([
    { role: 'system', content: 'Answer questions about the user\'s personal finances clearly and briefly using only the data provided.' },
    { role: 'user', content: `Data:\n${JSON.stringify(compact(data))}\n\nQuestion: ${question}` },
  ])
}

export function spendingNarrative(data) {
  return chat([
    { role: 'system', content: 'Write a short, friendly monthly spending narrative (3-5 sentences) with one actionable suggestion.' },
    { role: 'user', content: `Summarize spending patterns from this data:\n${JSON.stringify(compact(data))}` },
  ])
}
