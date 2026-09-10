import { useState } from 'react'
import { useStore, actions } from '../lib/store.js'
import { parseCode, PURCHASE_URL, TIERS } from '../lib/license.js'

function PlanBadge({ tier }) {
  return <span className={`badge ${tier}`}>{TIERS[tier]?.label || 'Free'} plan</span>
}

export default function LicensePanel({ notify }) {
  const plan = useStore((s) => s.plan)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')

  function activate(e) {
    e.preventDefault()
    setError('')
    const parsed = parseCode(code)
    if (!parsed) {
      setError('That doesn\'t look like a valid verification code.')
      return
    }
    if (parsed.expired) {
      setError('This code has expired. Renew your plan below.')
      return
    }
    actions.setPlan(parsed)
    setCode('')
    notify?.(`${TIERS[parsed.tier].label} plan activated`)
  }

  function deactivate() {
    actions.clearPlan()
    notify?.('Reverted to Free plan')
  }

  return (
    <div className="grid cols-2" style={{ alignItems: 'start' }}>
      {/* ── Code entry ─────────────────────────────────────────────── */}
      <div className="card license-box">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>Your Plan</h3>
          <PlanBadge tier={plan.tier} />
        </div>

        {plan.code ? (
          <>
            <div className="hint">
              Active plan: <b>{TIERS[plan.tier]?.label}</b>
              {plan.features?.length ? <> · {plan.features.length} feature(s) unlocked</> : null}
              {plan.exp ? <> · valid until {new Date(plan.exp * 1000).toLocaleDateString()}</> : null}
            </div>
            <div className="code-row">
              <input value={plan.code} readOnly />
              <button className="ghost danger" onClick={deactivate}>Remove</button>
            </div>
          </>
        ) : (
          <form onSubmit={activate} className="license-box">
            <div>
              <label>Enter your verification / purchase code</label>
              <div className="code-row">
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="eyJhbGciOi…  (paste the code from your purchase email)"
                  spellCheck={false}
                />
                <button type="submit" className="primary">Activate</button>
              </div>
            </div>
            {error && <div className="hint" style={{ color: 'var(--danger)' }}>{error}</div>}

            {/* Purchase CTA sits right next to the code entry, as requested. */}
            <div className="purchase">
              <b>Don't have a code yet?</b>
              <div className="hint">Buy a plan to unlock AI features — your code is emailed instantly, then paste it above.</div>
              <div className="plans">
                {['pro', 'max'].map((t) => (
                  <div className="plan-cta" key={t}>
                    <span className="name">{TIERS[t].label}</span>
                    <span className="price">{TIERS[t].price}</span>
                    <span className="hint">{TIERS[t].blurb}</span>
                    <a href={`${PURCHASE_URL}?plan=${t}`} target="_blank" rel="noreferrer">
                      <button className="primary" style={{ width: '100%' }} type="button">Get {TIERS[t].label}</button>
                    </a>
                  </div>
                ))}
              </div>
            </div>
          </form>
        )}
      </div>

      {/* ── Plan info ──────────────────────────────────────────────── */}
      <div className="card">
        <h3>What each plan unlocks</h3>
        <table>
          <thead><tr><th>Plan</th><th>Includes</th></tr></thead>
          <tbody>
            {Object.entries(TIERS).map(([k, v]) => (
              <tr key={k}>
                <td><span className={`badge ${k}`}>{v.label}</span></td>
                <td className="hint">{v.blurb}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <hr className="divider" />
        <div className="privacy-note">
          <span>🔒</span>
          <span>Your plan code and all financial data live only in this browser and in the JSON file you export. Nothing is uploaded to any server.</span>
        </div>
      </div>
    </div>
  )
}
