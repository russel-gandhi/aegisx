/**
 * Fixed demo identity (Phase 5, plan 05-05).
 *
 * Implements D-01's fixed demo identity: no credential is verified
 * anywhere. The selected role is client state only -- the server
 * (`backend/app/identity.py`'s `require_identity`) independently
 * re-derives and re-checks identity from the `X-User-Id`/`X-User-Role`
 * headers on every write-capable request, so this module is a convenience
 * for the operator, never a security control. A real auth swap replaces
 * `require_identity` on the server; nothing in this module is a
 * prerequisite for that swap.
 */

import { useSyncExternalStore } from 'react'

const STORAGE_KEY = 'aegisx.demo-identity'

export interface DemoIdentity {
  user_id: string
  role: string
}

// Bible Section 2 "Permission Matrix" role strings, transcribed verbatim
// -- including the slash in "QA/Compliance" -- matching
// `backend/app/identity.py`'s `DEMO_ROLES` exactly. 05-UI-SPEC.md writes
// the middle label "QA-Compliance" (hyphen) in its own prose, but the
// Bible is the source of truth on any drift (CLAUDE.md Rule 14), so no
// mapping table exists anywhere in this codebase between the two
// spellings: the label the operator sees is the same string the server
// matches, nothing is translated in between.
export const DEMO_IDENTITIES: readonly DemoIdentity[] = [
  { user_id: 'u-itsm-01', role: 'IT System Manager' },
  { user_id: 'u-qa-01', role: 'QA/Compliance' },
  { user_id: 'u-auditor-01', role: 'Auditor' },
]

const DEFAULT_IDENTITY = DEMO_IDENTITIES[0]

function isRecognizedIdentity(value: unknown): value is DemoIdentity {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<DemoIdentity>
  return DEMO_IDENTITIES.some(
    (identity) => identity.user_id === candidate.user_id && identity.role === candidate.role,
  )
}

function loadPersistedIdentity(): DemoIdentity {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_IDENTITY
    const parsed: unknown = JSON.parse(raw)
    // An unrecognised persisted role (e.g. a stale value from a previous
    // build, or a hand-edited localStorage entry) falls back to the
    // default identity rather than being sent to the server.
    return isRecognizedIdentity(parsed) ? parsed : DEFAULT_IDENTITY
  } catch {
    return DEFAULT_IDENTITY
  }
}

let currentIdentity: DemoIdentity = loadPersistedIdentity()
const listeners = new Set<() => void>()

export function getIdentity(): DemoIdentity {
  return currentIdentity
}

export function setIdentity(identity: DemoIdentity): void {
  currentIdentity = identity
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(identity))
  } catch {
    // Storage can fail (private browsing, quota) -- the in-memory value
    // still updates and every subscriber still re-renders; only
    // cross-reload persistence is lost.
  }
  for (const listener of listeners) {
    listener()
  }
}

export function subscribeIdentity(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

// Built on `useSyncExternalStore` (React 19, ships in this project's
// `react` dependency) so every consumer re-renders on a role change,
// including consumers that never call `setIdentity` themselves (e.g.
// `Actions.tsx` re-fetching the queue when the operator switches role
// from a different page's `RoleSelector` instance).
export function useIdentity(): DemoIdentity {
  return useSyncExternalStore(subscribeIdentity, getIdentity, getIdentity)
}

export function identityHeaders(): Record<string, string> {
  return {
    'X-User-Id': currentIdentity.user_id,
    'X-User-Role': currentIdentity.role,
  }
}
