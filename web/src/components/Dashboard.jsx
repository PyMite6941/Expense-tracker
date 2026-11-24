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
  cashFlowWindow, todayISO,
} from '../lib/analytics.js'

const GOOD = '#34d399'
const BAD = '#f87171'
const STATUS = {
  ok: { label: 'On track', color: 'var(--accent)', fill: GOOD },
  warning: { label: 'Near limit', color: 'var(--warn)', fill: '#fbbf24' },
  over: { label: 'Over budget', color: 'var(--danger)', fill: BAD },
}
const DAY_PRESETS = [7, 14, 30, 90, 180, 365]
const TOOLTIP_STYLE = { background: '#161b25', border: '1px solid #273041' }

function Segmented({ options, value, onChange, label }) {
  return (
    <div role="group" aria-label={label} style={{ display: 'inline-flex', gap: 4, flexWrap: 'wrap' }}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          className={value === o.value ? undefined : 'ghost'}
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          style={{ padding: '4px 10px', fontSize: 12.5 }}
        >{o.label}</button>
      ))}
    </div>
  )
}

function BudgetSquares({ budgets, cur }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 12 }}>
      {budgets.map((b) => {
        const st = STATUS[b.status]
        const c = b.currency || cur
        return (
          <div key={b.category} style={{ border: '1px solid var(--border)', borderTop: `3px solid ${st.fill}`, borderRadius: 10, padding: 12, background: 'var(--bg)', display: 'grid', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6, alignItems: 'baseline' }}>
              <b style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.category}</b>
              <span className="hint" style={{ color: st.color, whiteSpace: 'nowrap' }}>{st.label}</span>
            </div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{money(b.spent, c)}</div>
            <div className="hint">of {money(b.limit, c)} · {b.pct.toFixed(0)}%</div>
            <div style={{ height: 6, background: 'var(--bg-elev-2)', borderRadius: 99 }}>
              <div style={{ width: `${Math.min(100, b.pct)}%`, height: '100%', background: st.fill, borderRadius: 99 }} />
            </div>
            <div className="hint" style={b.remaining < 0 ? { color: 'var(--danger)' } : undefined}>
              {b.remaining >= 0 ? `${money(b.remaining, c)} left` : `Over by ${money(-b.remaining, c)}`}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function BudgetGraph({ budgets, cur }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(140, 44 * budgets.length + 40)}>
      <BarChart data={budgets} layout="vertical" margin={{ left: 8, right: 70 }} barGap={-18}>
        <CartesianGrid strokeDasharray="3 3" stroke="#273041" horizontal={false} />
        <XAxis type="number" stroke="#94a3b8" />
        <YAxis type="category" dataKey="category" stroke="#94a3b8" width={100} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(v, name) => [money(v, cur), name]}
          labelFormatter={(l) => {
            const b = budgets.find((r) => r.category === l)
            return b ? `${l} · ${b.pct.toFixed(0)}% · ${STATUS[b.status].label}` : l
          }}
        />
        {/* Pale full-length limit track with spend drawn over it. */}
        <Bar dataKey="limit" name="Limit" fill="#94a3b8" fillOpacity={0.25} barSize={18} radius={[0, 4, 4, 0]} isAnimationActive={false} />
        <Bar dataKey="spent" name="Spent" barSize={18} radius={[0, 4, 4, 0]}
          label={{ position: 'right', fill: '#94a3b8', fontSize: 12, formatter: (v) => money(v, cur) }}>
          {budgets.map((b) => <Cell key={b.category} fill={STATUS[b.status].fill} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function CashFlowCard({ data, cur }) {
  const [preset, setPreset] = useState(30)
  const [custom, setCustom] = useState(45)
  const [end, setEnd] = useState(todayISO())
  const days = preset === 'custom' ? Math.max(1, Math.min(3650, Math.floor(Number(custom)) || 1)) : preset
  const cf = useMemo(() => cashFlowWindow(data, days, end || todayISO()), [data, days, end])
  const unit = { day: 'day', week: '7-day block', month: 'calendar month' }[cf.bucket]

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>Money In vs Out — last {days} day{days === 1 ? '' : 's'}</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Segmented
            label="Time frame"
            options={[...DAY_PRESETS.map((d) => ({ value: d, label: `${d}d` })), { value: 'custom', label: 'Custom' }]}
            value={preset}
            onChange={setPreset}
          />
          {preset === 'custom' && (
            <input type="number" min={1} max={3650} value={custom} aria-label="Number of days"
              onChange={(e) => setCustom(e.target.value)} style={{ width: 80 }} />
          )}
          <input type="date" value={end} aria-label="Ending on"
            onChange={(e) => setEnd(e.target.value)} style={{ width: 'auto' }} />
        </div>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 12 }}>
        <Metric label="Money in" value={money(cf.totalIn, cur)} tone="var(--accent)" />
        <Metric label="Money out" value={money(cf.totalOut, cur)} tone="var(--danger)" />
        <Metric label="Net" value={money(cf.net, cur)} tone={cf.net >= 0 ? 'var(--accent)' : 'var(--danger)'} />
        <Metric label="Transactions" value={cf.transactions} />
      </div>

      {cf.transactions ? (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={cf.rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#273041" />
              <XAxis dataKey="label" stroke="#94a3b8" interval="preserveStartEnd" minTickGap={8} />
              <YAxis stroke="#94a3b8" />
              <Tooltip formatter={(v) => money(v, cur)} contentStyle={TOOLTIP_STYLE} />
              <Legend />
              <Bar dataKey="moneyIn" name="Money in" fill={GOOD} radius={[4, 4, 0, 0]} />
              <Bar dataKey="moneyOut" name="Money out" fill={BAD} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="hint">
            {cf.start} → {cf.end} · one bar pair per {unit}.
            {cf.currencies.length > 1 && ` Mixed currencies (${cf.currencies.join(', ').toUpperCase()}) are summed as entered, not converted.`}
          </div>
        </>
      ) : (
        <div className="empty">No income or expenses between {cf.start} and {cf.end}. Try a longer time frame or an earlier end date.</div>
      )}
    </div>
  )
}

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
  const [budgetView, setBudgetView] = useState('squares')
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

      {/* budgets: squares or graph */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Budget Status ({activeMonth})</h3>
          {budgets.length > 0 && (
            <Segmented
              label="Budget view"
              options={[{ value: 'squares', label: '▦ Squares' }, { value: 'graph', label: '📊 Graph' }]}
              value={budgetView}
              onChange={setBudgetView}
            />
          )}
        </div>
        {budgets.length === 0 ? <div className="empty">No budgets set.</div>
          : budgetView === 'graph' ? <BudgetGraph budgets={budgets} cur={cur} />
            : <BudgetSquares budgets={budgets} cur={cur} />}
        {budgets.some((b) => b.over) && (
          <div className="hint" style={{ color: 'var(--danger)', marginTop: 10 }}>
            🚨 Over budget: {budgets.filter((b) => b.over).map((b) => b.category).join(', ')}
          </div>
        )}
      </div>

      <CashFlowCard data={data} cur={cur} />

      {/* goals + renewals */}
      <div className="grid cols-2">
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
