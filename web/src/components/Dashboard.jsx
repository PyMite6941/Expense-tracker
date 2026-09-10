import { useMemo, useState } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid,
} from 'recharts'
import { useStore } from '../lib/store.js'
import { money, dominantCurrency } from '../lib/currency.js'
import {
  monthlyTotals, spendingByCategory, incomeVsExpenses, budgetUtilization,
  savingsRateHistory, netWorth, goalProgress, upcomingRenewals, financialHealthScore, thisMonth,
} from '../lib/analytics.js'

const PIE_COLORS = ['#6ea8fe', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee', '#fb923c']
const GRADE_COLOR = { A: '#34d399', B: '#6ea8fe', C: '#fbbf24', D: '#fb923c', F: '#f87171' }

function Metric({ label, value, sub, tone }) {
  return (
    <div className="card metric">
      <span className="label">{label}</span>
      <span className="value" style={tone ? { color: tone } : undefined}>{value}</span>
      {sub && <span className="hint">{sub}</span>}
    </div>
  )
}

export default function Dashboard() {
  const data = useStore((s) => s.data)

  // Month-scoped panels used to be pinned to thisMonth() with no control, so on
  // the 1st of a month the dashboard read as empty even with a full history.
  const knownMonths = useMemo(() => {
    const set = new Set([thisMonth()])
    for (const e of data.expenses) if (e.date) set.add(String(e.date).slice(0, 7))
    for (const i of data.income) if (i.date) set.add(String(i.date).slice(0, 7))
    return [...set].sort().reverse()
  }, [data.expenses, data.income])

  const [month, setMonth] = useState(thisMonth())
  const activeMonth = knownMonths.includes(month) ? month : knownMonths[0]

  const cur = dominantCurrency([...data.expenses, ...data.income])
  const ive = incomeVsExpenses(data, activeMonth)
  const months = monthlyTotals(data, 6)
  const byCat = spendingByCategory(data, activeMonth)
  const savings = savingsRateHistory(data, 6)
  const nw = netWorth(data)
  const goals = goalProgress(data)
  const renewals = upcomingRenewals(data, 30)
  const health = financialHealthScore(data)
  const budgets = budgetUtilization(data, activeMonth)

  const hasAny = data.expenses.length || data.income.length

  if (!hasAny) {
    return (
      <div className="card empty">
        <p style={{ fontSize: 16 }}>👋 Welcome! No data yet.</p>
        <p className="hint">Add expenses/income from the sidebar, or import a JSON file from <b>Data</b> to see your dashboard come alive.</p>
      </div>
    )
  }

  return (
    <div className="grid" style={{ gap: 18 }}>
      {/* month scope */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <label htmlFor="dash-month" className="hint">Showing</label>
        <select
          id="dash-month"
          value={activeMonth}
          onChange={(e) => setMonth(e.target.value)}
          style={{ width: 'auto', minWidth: 130 }}
        >
          {knownMonths.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        {activeMonth !== thisMonth() && (
          <button className="ghost" onClick={() => setMonth(thisMonth())}>Back to this month</button>
        )}
      </div>

      {/* headline metrics */}
      <div className="grid cols-4">
        <Metric label={`Income (${activeMonth})`} value={money(ive.income, cur)} tone="var(--accent)" />
        <Metric label={`Expenses (${activeMonth})`} value={money(ive.expenses, cur)} tone="var(--danger)" />
        <Metric label="Net" value={money(ive.net, cur)} tone={ive.net >= 0 ? 'var(--accent)' : 'var(--danger)'} />
        <Metric label="Net worth" value={money(nw.net, cur)} sub={`${money(nw.assets, cur)} assets · ${money(nw.liabilities, cur)} debt`} />
      </div>

      {/* health + charts */}
      <div className="grid cols-2">
        <div className="card">
          <h3>Financial Health</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 44, fontWeight: 800, color: GRADE_COLOR[health.grade] }}>{health.grade}</div>
              <div className="hint">{health.score} / 100</div>
            </div>
            <div style={{ flex: 1 }}>
              {Object.entries(health.pillars).map(([k, v]) => (
                <div key={k} style={{ marginBottom: 8 }}>
                  <div className="hint" style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{k.replace(/_/g, ' ')}</span><span>{v}</span>
                  </div>
                  <div style={{ height: 6, background: 'var(--bg)', borderRadius: 99 }}>
                    <div style={{ width: `${v}%`, height: '100%', background: 'var(--primary-2)', borderRadius: 99 }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Spending by Category ({activeMonth})</h3>
          {byCat.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={byCat} dataKey="value" nameKey="name" outerRadius={85} label={(e) => e.name}>
                  {byCat.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v) => money(v, cur)} contentStyle={{ background: '#161b25', border: '1px solid #273041' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <div className="empty">No expenses in {activeMonth}.</div>}
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>Income vs Expenses (6 months)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={months}>
              <CartesianGrid strokeDasharray="3 3" stroke="#273041" />
              <XAxis dataKey="label" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip formatter={(v) => money(v, cur)} contentStyle={{ background: '#161b25', border: '1px solid #273041' }} />
              <Legend />
              <Bar dataKey="income" fill="#34d399" radius={[4, 4, 0, 0]} />
              <Bar dataKey="expenses" fill="#f87171" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Savings Rate (%)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={savings}>
              <CartesianGrid strokeDasharray="3 3" stroke="#273041" />
              <XAxis dataKey="label" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip formatter={(v) => `${v}%`} contentStyle={{ background: '#161b25', border: '1px solid #273041' }} />
              <Line type="monotone" dataKey="rate" stroke="#6ea8fe" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* budgets + goals + renewals */}
      <div className="grid cols-3">
        <div className="card">
          <h3>Budget Usage</h3>
          {budgets.length ? budgets.map((b) => (
            <div key={b.category} style={{ marginBottom: 10 }}>
              <div className="hint" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{b.category}</span>
                <span style={b.over ? { color: 'var(--danger)' } : undefined}>{money(b.spent, cur)} / {money(b.limit, cur)}</span>
              </div>
              <div style={{ height: 6, background: 'var(--bg)', borderRadius: 99 }}>
                <div style={{ width: `${Math.min(100, b.pct)}%`, height: '100%', background: b.over ? 'var(--danger)' : 'var(--accent)', borderRadius: 99 }} />
              </div>
            </div>
          )) : <div className="empty">No budgets set.</div>}
        </div>

        <div className="card">
          <h3>Goals</h3>
          {goals.length ? goals.map((g) => (
            <div key={g.name} style={{ marginBottom: 10 }}>
              <div className="hint" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{g.name}</span><span>{g.percent.toFixed(0)}%{g.eta != null ? ` · ${g.eta}mo left` : ''}</span>
              </div>
              <div style={{ height: 6, background: 'var(--bg)', borderRadius: 99 }}>
                <div style={{ width: `${Math.min(100, g.percent)}%`, height: '100%', background: 'var(--primary-2)', borderRadius: 99 }} />
              </div>
            </div>
          )) : <div className="empty">No goals yet.</div>}
        </div>

        <div className="card">
          <h3>Upcoming Renewals (30d)</h3>
          {renewals.length ? renewals.map((r) => (
            <div key={r.name} className="hint" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span>{r.name}</span>
              <span>{money(r.price, r.currency)} · {r.days === 0 ? 'today' : `in ${r.days}d`}</span>
            </div>
          )) : <div className="empty">Nothing due soon.</div>}
        </div>
      </div>
    </div>
  )
}
