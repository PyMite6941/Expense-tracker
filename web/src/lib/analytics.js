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

export function budgetUtilization(data, month = thisMonth()) {
  const spentByCat = {}
  for (const e of rowsInMonth(data.expenses, month)) {
    spentByCat[e.tags] = (spentByCat[e.tags] || 0) + num(e.price)
  }
  return (data.budget || []).map((b) => {
    const spent = spentByCat[b.category] || 0
    const limit = num(b.amount)
    const pct = limit > 0 ? (spent / limit) * 100 : 0
    return { category: b.category, spent, limit, pct, currency: b.currency, over: spent > limit }
  })
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
