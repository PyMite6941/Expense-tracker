// Single source of truth for the data model. Drives both the CRUD forms/tables
// and the export/import bundle, so all 9 collections stay in lock-step with the
// original data.json shape.

export const CURRENCIES = [
  'USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD',
  'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other',
]

export const CATEGORIES = ['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other']

// field: { key, label, type, options?, step?, optional? }
export const COLLECTIONS = {
  expenses: {
    label: 'Expenses', singular: 'Expense', icon: '💸',
    fields: [
      { key: 'purchased', label: 'Item', type: 'text' },
      { key: 'price', label: 'Price', type: 'number', step: '0.01' },
      { key: 'tags', label: 'Category', type: 'select', options: CATEGORIES },
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
      { key: 'notes', label: 'Notes', type: 'text', optional: true },
    ],
    amountKey: 'price',
  },
  income: {
    label: 'Income', singular: 'Income', icon: '💰',
    fields: [
      { key: 'source', label: 'Source', type: 'text' },
      { key: 'amount', label: 'Amount', type: 'number', step: '0.01' },
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
      { key: 'notes', label: 'Notes', type: 'text', optional: true },
    ],
    amountKey: 'amount',
  },
  budget: {
    label: 'Budgets', singular: 'Budget', icon: '🎯',
    fields: [
      { key: 'category', label: 'Category', type: 'select', options: CATEGORIES },
      { key: 'amount', label: 'Monthly Limit', type: 'number', step: '0.01' },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
    ],
    amountKey: 'amount',
  },
  subscriptions: {
    label: 'Subscriptions', singular: 'Subscription', icon: '🔁',
    fields: [
      { key: 'name', label: 'Name', type: 'text' },
      { key: 'price', label: 'Price', type: 'number', step: '0.01' },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
      { key: 'startDate', label: 'Start Date', type: 'date' },
    ],
    amountKey: 'price',
  },
  goals: {
    label: 'Goals', singular: 'Goal', icon: '🏁',
    fields: [
      { key: 'name', label: 'Name', type: 'text' },
      { key: 'amount', label: 'Target', type: 'number', step: '0.01' },
      { key: 'startDate', label: 'Start Date', type: 'date' },
      { key: 'monthContribution', label: 'Monthly Contribution', type: 'number', step: '0.01' },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
    ],
    amountKey: 'amount',
  },
  assets: {
    label: 'Assets', singular: 'Asset', icon: '🏦',
    fields: [
      { key: 'name', label: 'Name', type: 'text' },
      { key: 'type', label: 'Type', type: 'text' },
      { key: 'value', label: 'Value', type: 'number', step: '0.01' },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
      { key: 'notes', label: 'Notes', type: 'text', optional: true },
    ],
    amountKey: 'value',
  },
  liabilities: {
    label: 'Liabilities', singular: 'Liability', icon: '📉',
    fields: [
      { key: 'name', label: 'Name', type: 'text' },
      { key: 'type', label: 'Type', type: 'text' },
      { key: 'balance', label: 'Balance', type: 'number', step: '0.01' },
      { key: 'interest_rate', label: 'Interest %', type: 'number', step: '0.01', optional: true },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
      { key: 'notes', label: 'Notes', type: 'text', optional: true },
    ],
    amountKey: 'balance',
  },
  recurring_expenses: {
    label: 'Recurring Expenses', singular: 'Recurring Expense', icon: '⏳',
    fields: [
      { key: 'purchased', label: 'Item', type: 'text' },
      { key: 'amount', label: 'Amount', type: 'number', step: '0.01' },
      { key: 'tags', label: 'Category', type: 'select', options: CATEGORIES },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
    ],
    amountKey: 'amount',
  },
  recurring_income: {
    label: 'Recurring Income', singular: 'Recurring Income', icon: '⏳',
    fields: [
      { key: 'source', label: 'Source', type: 'text' },
      { key: 'amount', label: 'Amount', type: 'number', step: '0.01' },
      { key: 'currency', label: 'Currency', type: 'select', options: CURRENCIES },
    ],
    amountKey: 'amount',
  },
}

export const COLLECTION_KEYS = Object.keys(COLLECTIONS)

export function emptyData() {
  const d = {}
  for (const k of COLLECTION_KEYS) d[k] = []
  return d
}
