// Pure client-side analytics — no server, no currency API. Amounts are summed
// numerically (single-currency assumption); mixed-currency data is still shown
// but not FX-converted, which keeps the app fully offline/privacy-first.

const num = (v) => Number(v) || 0
export const monthOf = (dateStr) => (dateStr ? String(dateStr).slice(0, 7) : '')
export const thisMonth = () => new Date().toISOString().slice(0, 7)

export function sum(rows, key) {
  return (rows || []).reduce((t, r) => t + num(r[key]), 0)
}

function rowsInMonth(rows, month) {
  return (rows || []).filter((r) => monthOf(r.date) === month)
}

export function monthlyTotals(data, monthsBack = 6) {
  const months = []
  const now = new Date()
  for (let i = monthsBack - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const m = d.toISOString().slice(0, 7)
    months.push({
      month: m,
      label: d.toLocaleString(undefined, { month: 'short' }),
      expenses: sum(rowsInMonth(data.expenses, m), 'price'),
      income: sum(rowsInMonth(data.income, m), 'amount'),
    })
  }
  return months
}

export function spendingByCategory(data, month = null) {
  const rows = month ? rowsInMonth(data.expenses, month) : data.expenses
  const totals = {}
  for (const e of rows || []) {
    const cat = e.tags || 'Other'
    totals[cat] = (totals[cat] || 0) + num(e.price)
  }
  return Object.entries(totals)
    .map(([name, value]) => ({ name, value: Math.round(value * 100) / 100 }))
    .sort((a, b) => b.value - a.value)
}

export function incomeVsExpenses(data, month = thisMonth()) {
  const income = sum(rowsInMonth(data.income, month), 'amount')
  const expenses = sum(rowsInMonth(data.expenses, month), 'price')
  return { income, expenses, net: income - expenses, month }
}

// Mirrors CLI/core/reports.py budget_vs_actual: case-insensitive category
// match, "warning" from 80% used, rows ordered over → warning → ok.
export const BUDGET_WARN_AT = 80
export function budgetUtilization(data, month = thisMonth()) {
  const spentByCat = {}
  for (const e of rowsInMonth(data.expenses, month)) {
    const k = String(e.tags || '').trim().toLowerCase()
    spentByCat[k] = (spentByCat[k] || 0) + num(e.price)
  }
  const order = { over: 0, warning: 1, ok: 2 }
  return (data.budget || []).map((b) => {
    const spent = Math.round((spentByCat[String(b.category || '').toLowerCase()] || 0) * 100) / 100
    const limit = num(b.amount)
    const pct = limit > 0 ? (spent / limit) * 100 : (spent ? 100 : 0)
    const status = spent > limit ? 'over' : pct >= BUDGET_WARN_AT ? 'warning' : 'ok'
    return {
      category: b.category, spent, limit, pct, currency: b.currency,
      remaining: Math.round((limit - spent) * 100) / 100, status, over: status === 'over',
    }
  }).sort((a, b) => order[a.status] - order[b.status] || b.pct - a.pct)
}

// ── Money in vs out over the last N days ────────────────────────────────────
// Mirrors CLI/core/reports.py cash_flow_window. Dates are handled as UTC
// calendar days so a timezone can't shift a transaction into the next bar.
const DAY_MS = 86400000
const toDay = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''))
  return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : null
}
const isoDay = (ms) => new Date(ms).toISOString().slice(0, 10)
const fmt = (ms, opts) => new Date(ms).toLocaleDateString(undefined, { timeZone: 'UTC', ...opts })

export const bucketFor = (days) => (days <= 31 ? 'day' : days <= 182 ? 'week' : 'month')

export function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function cashFlowWindow(data, days, endISO = todayISO()) {
  days = Math.max(1, Math.floor(Number(days) || 1))
  const end = toDay(endISO) ?? toDay(todayISO())
  const start = end - (days - 1) * DAY_MS
  const bucket = bucketFor(days)
  const key = (ms) => (bucket === 'day' ? isoDay(ms)
    : bucket === 'week' ? isoDay(start + Math.floor((ms - start) / (7 * DAY_MS)) * 7 * DAY_MS)
      : isoDay(ms).slice(0, 7))

  const rows = new Map()
  for (let ms = start; ms <= end; ms += DAY_MS) {
    const k = key(ms)
    if (!rows.has(k)) {
      const label = bucket === 'day' ? fmt(ms, { month: 'short', day: '2-digit' })
        : bucket === 'week' ? `Wk of ${fmt(ms, { month: 'short', day: '2-digit' })}`
          : fmt(ms, { month: 'short', year: 'numeric' })
      rows.set(k, { period: k, label, moneyIn: 0, moneyOut: 0 })
    }
  }
  let transactions = 0
  const currencies = new Set()
  const add = (items, field, amountKey) => {
    for (const x of items || []) {
      const ms = toDay(x.date)
      if (ms == null || ms < start || ms > end) continue
      rows.get(key(ms))[field] += num(x[amountKey])
      transactions++
      if (x.currency) currencies.add(String(x.currency).toLowerCase())
    }
  }
  add(data.income, 'moneyIn', 'amount')
  add(data.expenses, 'moneyOut', 'price')

  const r2 = (v) => Math.round(v * 100) / 100
  const out = [...rows.values()].map((r) => ({
    ...r, moneyIn: r2(r.moneyIn), moneyOut: r2(r.moneyOut), net: r2(r.moneyIn - r.moneyOut),
  }))
  const totalIn = r2(out.reduce((t, r) => t + r.moneyIn, 0))
  const totalOut = r2(out.reduce((t, r) => t + r.moneyOut, 0))
  return {
    start: isoDay(start), end: isoDay(end), days, bucket, rows: out,
    totalIn, totalOut, net: r2(totalIn - totalOut), transactions, currencies: [...currencies].sort(),
  }
}

export function savingsRateHistory(data, monthsBack = 6) {
  return monthlyTotals(data, monthsBack).map((m) => ({
    ...m,
    rate: m.income > 0 ? Math.round(((m.income - m.expenses) / m.income) * 100) : 0,
  }))
}

export function netWorth(data) {
  const assets = sum(data.assets, 'value')
  const liabilities = sum(data.liabilities, 'balance')
  return { assets, liabilities, net: assets - liabilities }
}

export function goalProgress(data) {
  return (data.goals || []).map((g) => {
    const target = num(g.amount)
    const monthly = num(g.monthContribution)
    let saved = 0
    if (g.startDate && monthly > 0) {
      const start = new Date(g.startDate)
      const now = new Date()
      const months = Math.max(0, (now.getFullYear() - start.getFullYear()) * 12 + (now.getMonth() - start.getMonth()))
      saved = Math.min(target, months * monthly)
    }
    const percent = target > 0 ? (saved / target) * 100 : 0
    const remaining = Math.max(0, target - saved)
    const etaMonths = monthly > 0 ? Math.ceil(remaining / monthly) : null
    return { name: g.name, target, saved, percent, currency: g.currency, eta: etaMonths }
  })
}

export function upcomingRenewals(data, daysAhead = 30) {
  const out = []
  const now = new Date()
  for (const s of data.subscriptions || []) {
    if (!s.startDate) continue
    const start = new Date(s.startDate)
    const next = new Date(now.getFullYear(), now.getMonth(), start.getDate())
    if (next < now) next.setMonth(next.getMonth() + 1)
    const days = Math.ceil((next - now) / 86400000)
    if (days <= daysAhead) {
      out.push({ name: s.name, price: num(s.price), currency: s.currency, days, date: next.toISOString().slice(0, 10) })
    }
  }
  return out.sort((a, b) => a.days - b.days)
}

// Composite 0–100 score with a letter grade, mirroring the backend's pillars.
export function financialHealthScore(data) {
  const { income, expenses } = incomeVsExpenses(data)
  const savingsRate = income > 0 ? (income - expenses) / income : 0
  const savingsPillar = Math.max(0, Math.min(100, savingsRate * 250)) // 40% savings -> 100

  const utils = budgetUtilization(data)
  const budgetPillar = utils.length
    ? Math.max(0, 100 - (utils.filter((u) => u.over).length / utils.length) * 100)
    : 60

  const monthlyIncome = income || 1
  const subCost = sum(data.subscriptions, 'price')
  const subPillar = Math.max(0, Math.min(100, 100 - (subCost / monthlyIncome) * 200))

  const goals = goalProgress(data)
  const goalPillar = goals.length ? goals.reduce((t, g) => t + Math.min(100, g.percent), 0) / goals.length : 50

  const score = Math.round(savingsPillar * 0.4 + budgetPillar * 0.25 + subPillar * 0.15 + goalPillar * 0.2)
  const grade = score >= 85 ? 'A' : score >= 70 ? 'B' : score >= 55 ? 'C' : score >= 40 ? 'D' : 'F'
  return {
    score, grade,
    pillars: {
      savings_rate: Math.round(savingsPillar),
      budget_adherence: Math.round(budgetPillar),
      subscription_burden: Math.round(subPillar),
      goal_consistency: Math.round(goalPillar),
    },
  }
}
