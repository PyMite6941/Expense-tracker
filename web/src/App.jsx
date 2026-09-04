import { useState, useCallback } from 'react'
import { useStore, downloadBundle } from './lib/store.js'
import { COLLECTIONS, COLLECTION_KEYS } from './lib/collections.js'
import { TIERS } from './lib/license.js'
import Dashboard from './components/Dashboard.jsx'
import DataTable from './components/DataTable.jsx'
import DataPanel from './components/DataPanel.jsx'
import LicensePanel from './components/LicensePanel.jsx'
import AIPanel from './components/AIPanel.jsx'

const NAV = [
  { key: 'dashboard', label: 'Dashboard', icon: '📊' },
  ...COLLECTION_KEYS.map((k) => ({ key: k, label: COLLECTIONS[k].label, icon: COLLECTIONS[k].icon, collection: true })),
  { key: 'ai', label: 'AI Insights', icon: '🤖' },
  { key: 'plan', label: 'Plan', icon: '🔑' },
  { key: 'data', label: 'Data (Import/Export)', icon: '💾' },
]

export default function App() {
  const [view, setView] = useState('dashboard')
  const [toast, setToast] = useState('')
  const plan = useStore((s) => s.plan)
  const data = useStore((s) => s.data)

  const notify = useCallback((msg) => {
    setToast(msg)
    window.clearTimeout(notify._t)
    notify._t = window.setTimeout(() => setToast(''), 2600)
  }, [])

  const current = NAV.find((n) => n.key === view) || NAV[0]

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo" />
          <b>GRID Tracker</b>
        </div>
        {NAV.map((n) => (
          <button
            key={n.key}
            className={`nav-item ${view === n.key ? 'active' : ''}`}
            onClick={() => setView(n.key)}
          >
            <span>{n.icon} {n.label}</span>
            {n.collection && <span className="count">{data[n.key].length}</span>}
          </button>
        ))}
        <div style={{ marginTop: 'auto', paddingTop: 16 }}>
          <span className={`badge ${plan.tier}`}>{TIERS[plan.tier]?.label} plan</span>
        </div>
      </aside>

      <main className="main">
        <div className="page-head">
          <div>
            <h1>{current.icon} {current.label}</h1>
            <div className="sub">Privacy-first · all data stays on your device</div>
          </div>
          <div className="topbar-actions">
            <button className="ghost" onClick={() => { downloadBundle(); notify('Exported bundle') }}>⬇ Export</button>
            <button className="primary" onClick={() => setView('plan')}>{plan.code ? 'Manage plan' : 'Enter code'}</button>
          </div>
        </div>

        {view === 'dashboard' && <Dashboard />}
        {view === 'ai' && <AIPanel notify={notify} />}
        {view === 'plan' && <LicensePanel notify={notify} />}
        {view === 'data' && <DataPanel notify={notify} />}
        {current.collection && <DataTable key={view} collectionKey={view} notify={notify} />}
      </main>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
