import { useRef, useState } from 'react'
import { useStore, actions, downloadBundle } from '../lib/store.js'
import { COLLECTIONS, COLLECTION_KEYS } from '../lib/collections.js'

export default function DataPanel({ notify }) {
  const data = useStore((s) => s.data)
  const plan = useStore((s) => s.plan)
  const fileRef = useRef(null)
  const [pending, setPending] = useState(null) // parsed bundle awaiting confirm

  const totalItems = COLLECTION_KEYS.reduce((t, k) => t + data[k].length, 0)

  function onPick(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const obj = JSON.parse(reader.result)
        const count = COLLECTION_KEYS.reduce((t, k) => t + (Array.isArray((obj.data || obj)[k]) ? (obj.data || obj)[k].length : 0), 0)
        setPending({ obj, count, tier: obj.plan?.tier || 'free', name: file.name })
      } catch {
        notify?.('That file is not valid JSON')
      }
    }
    reader.readAsText(file)
    e.target.value = '' // allow re-picking the same file
  }

  function confirmImport() {
    actions.importBundle(pending.obj)
    notify?.(`Imported ${pending.count} item(s) from ${pending.name}`)
    setPending(null)
  }

  function reset() {
    if (confirm('Erase ALL local data and revert to Free plan? Export a backup first if unsure.')) {
      actions.resetAll()
      notify?.('All local data cleared')
    }
  }

  return (
    <div className="grid" style={{ gap: 18 }}>
      <div className="privacy-note">
        <span>🔒</span>
        <span>
          Privacy-first: your data never leaves this device. It lives in this browser and in the single
          JSON file you export — which bundles your <b>plan + verification code + all records</b> together.
          Back it up regularly; clearing your browser data will erase it.
        </span>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>Export</h3>
          <p className="hint">
            Download everything as one <code>.json</code> file: your {totalItems} record(s), plus your
            {' '}<b>{plan.tier}</b> plan and verification code. Import it on any device to restore.
          </p>
          <button className="primary" onClick={() => { downloadBundle(); notify?.('Exported bundle') }}>
            ⬇ Export all to JSON
          </button>
        </div>

        <div className="card">
          <h3>Import</h3>
          <p className="hint">Load a previously exported <code>.json</code>. This replaces your current local data.</p>
          <input ref={fileRef} type="file" accept="application/json,.json" onChange={onPick} style={{ display: 'none' }} />
          <button onClick={() => fileRef.current?.click()}>⬆ Choose JSON file…</button>

          {pending && (
            <div className="purchase" style={{ marginTop: 14 }}>
              <b>Import “{pending.name}”?</b>
              <div className="hint">{pending.count} record(s) · plan: <b>{pending.tier}</b>. This overwrites your current local data.</div>
              <div className="form-actions">
                <button className="primary" onClick={confirmImport}>Replace &amp; import</button>
                <button className="ghost" onClick={() => setPending(null)}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Contents</h3>
        <table>
          <thead><tr><th>Collection</th><th style={{ textAlign: 'right' }}>Records</th></tr></thead>
          <tbody>
            {COLLECTION_KEYS.map((k) => (
              <tr key={k}>
                <td>{COLLECTIONS[k].icon} {COLLECTIONS[k].label}</td>
                <td style={{ textAlign: 'right' }}>{data[k].length}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <hr className="divider" />
        <button className="ghost danger" onClick={reset}>Erase all local data</button>
      </div>
    </div>
  )
}
