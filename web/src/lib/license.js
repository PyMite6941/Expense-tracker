// License / verification-code handling — fully client-side (privacy-first).
//
// Codes are the HS256 JWTs minted by the store's auth-service. We can't verify
// the signature in the browser without exposing the shared secret, so we DECODE
// the payload to read the plan (tier + features) the user paid for and trust it
// locally. That's fine for a local-only app; a signed/asymmetric token or a
// serverless /verify route can be dropped in later without changing the UI.

// Where to send users who want to buy a plan — the GRID store's license page,
// which runs the Base-USDC redeem flow and returns the JWT to paste back here.
// Override at build time with VITE_PURCHASE_URL.
export const PURCHASE_URL =
  import.meta.env.VITE_PURCHASE_URL || 'https://grid-store.pages.dev/codes'

export const TIERS = {
  free: { label: 'Free', price: '$0', blurb: 'Local tracking, charts & exports' },
  pro: { label: 'Pro', price: '$9', blurb: 'AI budget advisor, forecasting, anomalies' },
  max: { label: 'Max', price: '$19', blurb: 'Everything in Pro + net worth, coaching, DNA' },
}

function b64urlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/')
  while (str.length % 4) str += '='
  try {
    return decodeURIComponent(
      atob(str)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
  } catch {
    return atob(str)
  }
}

// Parse a verification code into a plan. Returns null if it doesn't look valid.
export function parseCode(code) {
  const token = (code || '').trim()
  if (!token) return null
  const parts = token.split('.')
  if (parts.length !== 3) return null
  let payload
  try {
    payload = JSON.parse(b64urlDecode(parts[1]))
  } catch {
    return null
  }
  const tier = (payload.tier || 'free').toLowerCase()
  if (!TIERS[tier]) return null
  // Expiry check (JWT exp is seconds since epoch).
  if (payload.exp && Date.now() / 1000 > payload.exp) {
    return { tier: 'free', features: [], code: token, expired: true, sub: payload.sub }
  }
  return {
    tier,
    features: payload.features || [],
    code: token,
    sub: payload.sub || null,
    exp: payload.exp || null,
  }
}

export const FREE_PLAN = { tier: 'free', features: [], code: null }

export function hasFeature(plan, feature) {
  return !!plan && Array.isArray(plan.features) && plan.features.includes(feature)
}
