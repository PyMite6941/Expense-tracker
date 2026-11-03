import { useState } from 'react'
import { COLLECTIONS } from '../lib/collections.js'
import { useStore, actions } from '../lib/store.js'
import { money } from '../lib/currency.js'

function blankForm(fields) {
  const f = {}
  for (const field of fields) {
    if (field.type === 'select') f[field.key] = field.options[0]
    else if (field.type === 'number') f[field.key] = ''
    else if (field.type === 'date') f[field.key] = new Date().toISOString().slice(0, 10)
    else f[field.key] = ''
  }
  return f
}

function coerce(fields, form) {
  const out = {}
  for (const field of fields) {
    let v = form[field.key]
    if (field.type === 'number') v = v === '' || v === null ? 0 : Number(v)
    out[field.key] = v
  }
  return out
}

export default function DataTable({ collectionKey, notify }) {
  const cfg = COLLECTIONS[collectionKey]
  const rows = useStore((s) => s.data[collectionKey])
  const [form, setForm] = useState(() => blankForm(cfg.fields))
  const [editingId, setEditingId] = useState(null)
  // Delete is destructive and used to fire on a single click. Arm it first:
  // the button turns into "Confirm?" and only the second click removes the row.
  const [pendingDelete, setPendingDelete] = useState(null)

  // Newest first when the collection carries a date — insertion order is
  // useless once you have more than a screenful of expenses.
  const dateKey = cfg.fields.find((f) => f.type === 'date')?.key
  const sortedRows = dateKey
    ? [...rows].sort((a, b) => String(b[dateKey] ?? '').localeCompare(String(a[dateKey] ?? '')))
    : rows

  const total = cfg.amountKey
    ? rows.reduce((sum, r) => sum + (Number(r[cfg.amountKey]) || 0), 0)
    : null

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  function submit(e) {
    e.preventDefault()
    // require the first non-optional text/number field to be filled
    const required = cfg.fields.filter((f) => !f.optional)
    for (const f of required) {
      if (form[f.key] === '' || form[f.key] === null || form[f.key] === undefined) {
        notify?.(`${f.label} is required`)
        return
      }
    }
    const payload = coerce(cfg.fields, form)
    if (editingId) {
      actions.updateItem(collectionKey, editingId, payload)
      notify?.(`${cfg.singular} updated`)
    } else {
      actions.addItem(collectionKey, payload)
      notify?.(`${cfg.singular} added`)
    }
    setForm(blankForm(cfg.fields))
    setEditingId(null)
  }

  function startEdit(row) {
    const f = {}
    for (const field of cfg.fields) f[field.key] = row[field.key] ?? (field.type === 'number' ? '' : '')
    setForm(f)
    setEditingId(row.id)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function remove(id) {
    if (pendingDelete !== id) { setPendingDelete(id); return }
    actions.deleteItem(collectionKey, id)
    setPendingDelete(null)
    if (editingId === id) { setEditingId(null); setForm(blankForm(cfg.fields)) }
    notify?.(`${cfg.singular} deleted`)
  }

  return (
    <div className="grid" style={{ gap: 18 }}>
      <div className="card">
        <h3>{editingId ? `Edit ${cfg.singular}` : `Add ${cfg.singular}`}</h3>
        <form onSubmit={submit}>
          <div className="form-grid">
            {cfg.fields.map((field) => (
              <div key={field.key}>
                <label>{field.label}{field.optional ? ' (optional)' : ''}</label>
                {field.type === 'select' ? (
                  <select value={form[field.key]} onChange={(e) => set(field.key, e.target.value)}>
                    {field.options.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : (
                  <input
                    type={field.type}
                    step={field.step}
                    value={form[field.key]}
                    onChange={(e) => set(field.key, e.target.value)}
                    placeholder={field.label}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="form-actions">
            <button type="submit" className="primary">{editingId ? 'Save Changes' : `Add ${cfg.singular}`}</button>
            {editingId && (
              <button type="button" className="ghost" onClick={() => { setEditingId(null); setForm(blankForm(cfg.fields)) }}>
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>

      <div className="card">
        <h3>{cfg.label} <span className="hint">({rows.length})</span></h3>
        {rows.length === 0 ? (
          <div className="empty">No {cfg.label.toLowerCase()} yet. Add your first above.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  {cfg.fields.map((f) => <th key={f.key}>{f.label}</th>)}
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row) => (
                  <tr key={row.id}>
                    {cfg.fields.map((f) => (
                      <td key={f.key}>
                        {f.key === cfg.amountKey
                          ? money(row[f.key], row.currency)
                          : String(row[f.key] ?? '—')}
                      </td>
                    ))}
                    <td>
                      <div className="row-actions">
                        <button className="ghost" onClick={() => startEdit(row)}>Edit</button>
                        <button
                          className="ghost danger"
                          onClick={() => remove(row.id)}
                          onBlur={() => pendingDelete === row.id && setPendingDelete(null)}
                        >
                          {pendingDelete === row.id ? 'Confirm?' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              {total !== null && rows.length > 0 && (
                <tfoot>
                  <tr>
                    <td colSpan={cfg.fields.length} style={{ fontWeight: 600 }}>
                      Total ({rows.length} {rows.length === 1 ? 'row' : 'rows'})
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>
                      {money(total, rows[0]?.currency)}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
