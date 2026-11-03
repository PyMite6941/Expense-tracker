// Local-only store. All state lives in the browser (localStorage) — nothing is
// ever sent to a server. The whole thing round-trips to a single JSON bundle
// that carries the user's plan + verification code + all their data.

import { useSyncExternalStore } from 'react'
import { emptyData, COLLECTION_KEYS } from './collections.js'
import { FREE_PLAN } from './license.js'

const LS_KEY = 'grid-expense-tracker/v2'
export const BUNDLE_VERSION = 2

function freshState() {
  return { plan: { ...FREE_PLAN }, data: emptyData(), meta: { updatedAt: null } }
}

function load() {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return freshState()
    const parsed = JSON.parse(raw)
    return normalize(parsed)
  } catch {
    return freshState()
  }
}

// Coerce any incoming object (localStorage or an imported file) into a valid,
// complete state — missing collections become empty arrays.
function normalize(obj) {
  const base = freshState()
  if (!obj || typeof obj !== 'object') return base
  const src = obj.data && typeof obj.data === 'object' ? obj.data : obj
  const data = emptyData()
  for (const k of COLLECTION_KEYS) {
    // Spread FIRST, then set id. The other order let an incoming `"id": null`
    // (or 0, or an explicit undefined) overwrite the generated one, which meant
    // imported rows could share a null key — breaking React keys, edit and delete.
    if (Array.isArray(src[k])) {
      data[k] = src[k]
        .filter((it) => it && typeof it === 'object')
        .map((it) => ({ ...it, id: it.id || uid() }))
    }
  }
  const plan = obj.plan && typeof obj.plan === 'object' ? obj.plan : base.plan
  return {
    plan: { tier: plan.tier || 'free', features: plan.features || [], code: plan.code || null, sub: plan.sub || null, exp: plan.exp || null },
    data,
    meta: { updatedAt: obj.meta?.updatedAt || null },
  }
}

function uid() {
  return (crypto?.randomUUID?.() || 'id-' + Math.random().toString(36).slice(2) + Date.now())
}

let state = load()
const listeners = new Set()

function persist() {
  state = { ...state, meta: { updatedAt: new Date().toISOString() } }
  try { localStorage.setItem(LS_KEY, JSON.stringify(state)) } catch { /* quota */ }
  listeners.forEach((l) => l())
}

// ── external store plumbing (useSyncExternalStore) ──────────────────────────
function subscribe(cb) { listeners.add(cb); return () => listeners.delete(cb) }
function getSnapshot() { return state }

export function useStore(selector = (s) => s) {
  return useSyncExternalStore(subscribe, () => selector(state), () => selector(state))
}

// ── actions ─────────────────────────────────────────────────────────────────
export const actions = {
  addItem(collection, item) {
    // id last, so a stray `id` on the incoming form payload can never collide
    // with an existing row.
    state = { ...state, data: { ...state.data, [collection]: [...state.data[collection], { ...item, id: uid() }] } }
    persist()
  },
  updateItem(collection, id, patch) {
    state = {
      ...state,
      data: {
        ...state.data,
        [collection]: state.data[collection].map((it) => (it.id === id ? { ...it, ...patch } : it)),
      },
    }
    persist()
  },
  deleteItem(collection, id) {
    state = { ...state, data: { ...state.data, [collection]: state.data[collection].filter((it) => it.id !== id) } }
    persist()
  },
  setPlan(plan) {
    state = { ...state, plan: { tier: 'free', features: [], code: null, ...plan } }
    persist()
  },
  clearPlan() {
    state = { ...state, plan: { ...FREE_PLAN } }
    persist()
  },
  applyAllRecurring() {
    const month = new Date().toISOString().slice(0, 7)
    const dateStr = `${month}-01`
    const newExp = state.data.recurring_expenses.map((r) => ({
      id: uid(), price: r.amount, purchased: r.purchased, tags: r.tags,
      currency: r.currency, date: dateStr, notes: 'Applied from recurring',
    }))
    const newInc = state.data.recurring_income.map((r) => ({
      id: uid(), amount: r.amount, source: r.source, currency: r.currency,
      date: dateStr, notes: 'Applied from recurring',
    }))
    state = {
      ...state,
      data: {
        ...state.data,
        expenses: [...state.data.expenses, ...newExp],
        income: [...state.data.income, ...newInc],
      },
    }
    persist()
    return newExp.length + newInc.length
  },
  importBundle(obj) {
    state = normalize(obj)
    persist()
  },
  resetAll() {
    state = freshState()
    persist()
  },
}

// ── single-file bundle: plan + verification code + all data ─────────────────
export function exportBundle() {
  return {
    app: 'grid-expense-tracker',
    version: BUNDLE_VERSION,
    exportedAt: new Date().toISOString(),
    plan: state.plan,          // includes tier, features, and verification code
    data: state.data,
  }
}

export function downloadBundle() {
  const blob = new Blob([JSON.stringify(exportBundle(), null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const stamp = new Date().toISOString().slice(0, 10)
  a.href = url
  a.download = `expense-tracker-${stamp}.json`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
