const SYMBOLS = {
  usd: '$', eur: '€', gbp: '£', jpy: '¥', cny: '¥', inr: '₹', krw: '₩', thb: '฿',
  aud: 'A$', cad: 'C$', chf: 'Fr', sgd: 'S$', hkd: 'HK$', nzd: 'NZ$', sek: 'kr',
  nok: 'kr', dkk: 'kr', brl: 'R$', zar: 'R', btc: '₿', eth: 'Ξ', usdc: 'USDC ', sol: 'SOL ',
}

export function symbol(currency) {
  if (!currency) return '$'
  return SYMBOLS[currency.toLowerCase()] || currency.toUpperCase() + ' '
}

export function money(amount, currency = 'usd') {
  const n = Number(amount) || 0
  const sym = symbol(currency)
  return `${sym}${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

// Dominant currency across a set of rows (for headline metrics).
export function dominantCurrency(rows) {
  const counts = {}
  for (const r of rows || []) {
    const c = (r.currency || 'usd').toLowerCase()
    counts[c] = (counts[c] || 0) + 1
  }
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'usd'
}
