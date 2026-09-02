import { useEffect, useState } from 'react'
import {
  fetchChainVerification,
  fetchTrustCentre,
  type ChainVerificationResponse,
  type LLMProviderInfo,
  type TrustCentreResponse,
} from '../lib/api'

// Bible Section 11.8: "The transparency hub displaying current LLM
// provider configurations, the active OPA Rego policy bundle version, and
// the live Audit Chain Integrity widget. The widget allows users to
// execute verify_chain() and visually confirms the cryptographic
// soundness of the event log." Every field on this page comes from either
// `GET /api/trust-centre` or `GET /api/audit/verify` -- no client-side
// guessing of a "policy bundle version" beyond the real file list OPA
// itself loads.
type CallStatus = 'loading' | 'ready' | 'error'

function ProviderRow({ entry, rank }: { entry: LLMProviderInfo; rank: number }) {
  return (
    <tr className="border-b border-white/[0.06] last:border-0">
      <td className="px-4 py-3">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/[0.06] text-xs font-semibold text-ink-muted">
          {rank}
        </span>
      </td>
      <td className="px-4 py-3 font-medium text-ink">{entry.provider}</td>
      <td className="px-4 py-3 font-mono text-xs text-ink-muted">{entry.model}</td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {entry.use_for.map((task) => (
            <span key={task} className="badge badge-neutral">
              {task}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3">
        {entry.requires_api_key ? (
          <span className="text-xs text-ink-faint">Hosted (API key)</span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-mint">
            <svg className="h-3 w-3" viewBox="0 0 8 8" fill="currentColor" aria-hidden="true">
              <circle cx="4" cy="4" r="4" />
            </svg>
            Local, no key
          </span>
        )}
      </td>
    </tr>
  )
}

function ChainWidget() {
  const [status, setStatus] = useState<CallStatus>('loading')
  const [data, setData] = useState<ChainVerificationResponse | null>(null)
  const [checking, setChecking] = useState(false)

  const runVerify = () => {
    setChecking(true)
    fetchChainVerification()
      .then((res) => {
        setData(res)
        setStatus('ready')
      })
      .catch(() => setStatus('error'))
      .finally(() => setChecking(false))
  }

  useEffect(runVerify, [])

  const tampered = data?.status === 'TAMPERED'

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[15px] font-semibold text-ink">Audit Chain Integrity</p>
          <p className="mt-1 text-sm text-ink-muted">
            Every audit event is hash-chained to the one before it. Verifying re-walks the chain
            and recomputes each hash from scratch.
          </p>
        </div>
        <button
          type="button"
          onClick={runVerify}
          disabled={checking}
          className="btn btn-secondary shrink-0"
        >
          {checking ? 'Verifying…' : 'Re-verify Chain'}
        </button>
      </div>

      <div className="mt-4">
        {status === 'loading' && <p className="text-sm text-ink-muted">Verifying&hellip;</p>}
        {status === 'error' && <p className="text-sm text-red">Couldn&rsquo;t reach the audit route.</p>}
        {status === 'ready' && data && (
          <div
            className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${
              tampered
                ? 'border-red-500/30 bg-red-soft'
                : 'border-mint/30 bg-mint-soft'
            }`}
          >
            <svg
              className={`h-8 w-8 shrink-0 ${tampered ? 'text-red' : 'text-mint'}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden="true"
            >
              {tampered ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="m9 12.75 2.25 2.25 6-6m6 3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              )}
            </svg>
            <div>
              <p className={`font-semibold ${tampered ? 'text-red' : 'text-mint'}`}>
                {tampered ? 'TAMPERED' : 'VERIFIED'}
              </p>
              <p className="mt-0.5 text-xs text-ink-faint">
                {data.events_checked !== null
                  ? `${data.events_checked} event${data.events_checked === 1 ? '' : 's'} checked`
                  : 'No events in the chain yet'}
                {tampered && data.broken_at_index !== null && ` — break detected at index ${data.broken_at_index}`}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function TrustCentre() {
  const [status, setStatus] = useState<CallStatus>('loading')
  const [data, setData] = useState<TrustCentreResponse | null>(null)

  useEffect(() => {
    fetchTrustCentre()
      .then((res) => {
        setData(res)
        setStatus('ready')
      })
      .catch(() => setStatus('error'))
  }, [])

  return (
    <div>
      <p className="eyebrow">Transparency hub</p>
      <h1 className="mt-1 text-[28px] font-bold text-ink">Trust Centre</h1>
      <p className="mt-2 max-w-2xl text-[13.5px] text-ink-muted">
        The transparency hub: which model answered your last question, what happens when it
        can&rsquo;t, the active policy bundle, and whether the audit log has been tampered with.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChainWidget />

        <div className="card p-5">
          <p className="text-[15px] font-semibold text-ink">OPA Policy Bundle</p>
          <p className="mt-1 text-sm text-ink-muted">
            Rego policy files currently loaded by the OPA sidecar &mdash; deterministic rules, zero
            LLM in the decision path.
          </p>
          <div className="mt-4">
            {status === 'loading' && <p className="text-sm text-ink-muted">Loading&hellip;</p>}
            {status === 'error' && <p className="text-sm text-red">Couldn&rsquo;t load policy bundle info.</p>}
            {status === 'ready' && data && (
              <>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-semibold text-ink">{data.opa_policy_count}</span>
                  <span className="text-sm text-ink-muted">
                    active {data.opa_policy_count === 1 ? 'policy file' : 'policy files'}
                  </span>
                </div>
                <ul className="mt-3 space-y-1.5">
                  {data.opa_policy_files.map((file) => (
                    <li key={file} className="flex items-center gap-2 font-mono text-xs text-ink-muted">
                      <svg className="h-3.5 w-3.5 shrink-0 text-ink-faint" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path
                          fillRule="evenodd"
                          d="M4 4a2 2 0 0 1 2-2h5.586A2 2 0 0 1 13 2.586L15.414 5A2 2 0 0 1 16 6.414V16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4Z"
                          clipRule="evenodd"
                        />
                      </svg>
                      {file}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="card mt-6 p-5">
        <p className="text-[15px] font-semibold text-ink">LLM Provider Cascade</p>
        <p className="mt-1 text-sm text-ink-muted">
          The order every AI-narrated response is attempted in. A failing hop cascades to the
          next automatically &mdash; deterministic findings never depend on any of these succeeding.
        </p>
        <div className="mt-4 overflow-x-auto">
          {status === 'loading' && <p className="text-sm text-ink-muted">Loading&hellip;</p>}
          {status === 'error' && <p className="text-sm text-red">Couldn&rsquo;t load provider configuration.</p>}
          {status === 'ready' && data && (
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/[0.08] text-xs tracking-wide text-ink-faint uppercase">
                  <th className="px-4 py-2 font-medium">Order</th>
                  <th className="px-4 py-2 font-medium">Provider</th>
                  <th className="px-4 py-2 font-medium">Model</th>
                  <th className="px-4 py-2 font-medium">Handles</th>
                  <th className="px-4 py-2 font-medium">Auth</th>
                </tr>
              </thead>
              <tbody>
                {data.llm_cascade.map((entry, i) => (
                  <ProviderRow key={entry.provider_key} entry={entry} rank={i + 1} />
                ))}
                <tr className="border-t-2 border-white/[0.08]">
                  <td className="px-4 py-3">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/[0.06] text-xs text-ink-faint">
                      E
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-ink">
                    {data.embedding_provider.provider}
                    <span className="badge badge-neutral ml-2">
                      embeddings
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-muted">{data.embedding_provider.model}</td>
                  <td className="px-4 py-3 text-xs text-ink-muted">document &amp; query vectors</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 text-xs text-mint">
                      <svg className="h-3 w-3" viewBox="0 0 8 8" fill="currentColor" aria-hidden="true">
                        <circle cx="4" cy="4" r="4" />
                      </svg>
                      Local, no key
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
