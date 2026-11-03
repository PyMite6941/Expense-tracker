import { useState } from 'react'
import { useStore } from '../lib/store.js'
import { hasFeature } from '../lib/license.js'
import {
  PROVIDERS, getAIConfig, setAIConfig, aiConfigured,
  recommendBudgets, askQuestion, spendingNarrative,
} from '../lib/ai.js'

export default function AIPanel({ notify }) {
  const data = useStore((s) => s.data)
  const plan = useStore((s) => s.plan)
  const [cfg, setCfg] = useState(getAIConfig())
  const [savedKey, setSavedKey] = useState(aiConfigured())
  const [question, setQuestion] = useState('')
  const [output, setOutput] = useState('')
  const [busy, setBusy] = useState(false)

  // AI is a paid feature in the original product; gate on any Pro/Max feature.
  const unlocked = plan.tier === 'pro' || plan.tier === 'max' ||
    hasFeature(plan, 'advanced_categorization') || hasFeature(plan, 'net_worth')

  function saveKey() {
    setAIConfig({ key: cfg.key, provider: cfg.provider })
    setSavedKey(!!cfg.key)
    notify?.(cfg.key ? 'AI key saved locally' : 'AI key cleared')
  }

  async function run(fn) {
    setBusy(true); setOutput('')
    try {
      setOutput(await fn())
    } catch (e) {
      setOutput('')
      notify?.(e.message || 'AI request failed')
    } finally {
      setBusy(false)
    }
  }

  if (!unlocked) {
    return (
      <div className="card">
        <h3>AI Insights</h3>
        <div className="privacy-note" style={{ marginBottom: 14 }}>
          <span>🔒</span>
          <span>AI features are part of the <b>Pro</b> and <b>Max</b> plans. Activate your code in <b>Plan</b> to unlock them.</span>
        </div>
        <p className="hint">Once unlocked, you bring your own Groq/OpenRouter API key — requests go straight from your browser to the provider, never through our servers.</p>
      </div>
    )
  }

  return (
    <div className="grid" style={{ gap: 18 }}>
      <div className="card">
        <h3>AI Provider (bring your own key)</h3>
        <div className="privacy-note" style={{ marginBottom: 14 }}>
          <span>🔒</span>
          <span>Your key is stored only in this browser. Your finance data is sent to the chosen provider <b>only when you run an action below</b>.</span>
        </div>
        <div className="form-grid">
          <div>
            <label>Provider</label>
            <select value={cfg.provider} onChange={(e) => setCfg({ ...cfg, provider: e.target.value })}>
              {Object.entries(PROVIDERS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
          <div>
            <label>API key</label>
            <input
              type="password"
              value={cfg.key}
              onChange={(e) => setCfg({ ...cfg, key: e.target.value })}
              placeholder={PROVIDERS[cfg.provider]?.keyHint}
            />
          </div>
        </div>
        <div className="form-actions">
          <button className="primary" onClick={saveKey}>Save key</button>
          {savedKey && <span className="hint" style={{ alignSelf: 'center' }}>✓ key saved</span>}
        </div>
      </div>

      <div className="card">
        <h3>Insights</h3>
        <div className="topbar-actions" style={{ flexWrap: 'wrap' }}>
          <button disabled={busy || !savedKey} onClick={() => run(() => recommendBudgets(data))}>💡 Recommend budgets</button>
          <button disabled={busy || !savedKey} onClick={() => run(() => spendingNarrative(data))}>📝 Spending narrative</button>
        </div>
        <hr className="divider" />
        <label>Ask anything about your finances</label>
        <div className="code-row">
          <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. Where can I cut back this month?" />
          <button className="primary" disabled={busy || !savedKey || !question.trim()} onClick={() => run(() => askQuestion(data, question))}>Ask</button>
        </div>
        {busy && <p className="hint" style={{ marginTop: 14 }}>Thinking…</p>}
        {output && (
          <pre style={{ whiteSpace: 'pre-wrap', marginTop: 14, background: 'var(--bg)', padding: 14, borderRadius: 10, border: '1px solid var(--border)', fontFamily: 'inherit' }}>
            {output}
          </pre>
        )}
        {!savedKey && <p className="hint" style={{ marginTop: 12 }}>Add and save an API key above to enable these actions.</p>}
      </div>
    </div>
  )
}
