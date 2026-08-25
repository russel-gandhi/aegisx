import { useEffect, useRef, useState } from 'react'
import AgentTopologyCanvas from '../components/AgentTopologyCanvas'
import { connectCopilotStream, type CopilotStreamFrame } from '../lib/ws'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

// A value generated once per mount is sufficient for this plan's contract
// -- nothing yet correlates a session id with a server-side record. Real
// session issuance is Phase 5's job (C2 RBAC, SENT-4-01).
function generateSessionId(): string {
  return `copilot-${Math.random().toString(36).slice(2, 10)}`
}

export default function Copilot() {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [frames, setFrames] = useState<CopilotStreamFrame[]>([])
  const sessionIdRef = useRef(generateSessionId())

  useEffect(() => {
    const handle = connectCopilotStream(sessionIdRef.current, {
      onOpen: () => setStatus('connected'),
      onFrame: (frame) => {
        setFrames((prev) => [...prev, frame])
        if (frame.event === 'connected') {
          handle.send('test-event')
        }
      },
      onError: () => setStatus('error'),
      onClose: () => setStatus('disconnected'),
    })

    return () => {
      handle.close()
    }
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Ask GxP Copilot</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        A natural-language chat interface backed by the C2 → A0 → [A1…A6] → C1 → A7 → C3 agent
        pipeline. The canvas below visualizes live agent execution state as a question moves
        through orchestration, evidence verification, and remediation.
      </p>

      <div className="mt-6 rounded border border-slate-800 bg-slate-900/50 p-4">
        <p className="text-sm text-slate-300">
          Connection status: <span data-testid="ws-status">{status}</span>
        </p>
        <ul className="mt-2 space-y-1 text-sm text-slate-400" data-testid="ws-frames">
          {frames.map((frame, i) => (
            <li key={i}>
              {frame.event === 'connected' && `connected (session ${frame.session_id})`}
              {frame.event === 'echo' && `echo: ${frame.payload}`}
              {/* Phase 5 (05-05) added `action_proposal_created` to this
                  stream's frame union (see lib/ws.ts). This page does not
                  yet render that frame shape -- the live Approval Centre
                  (pages/Actions.tsx) is where it is consumed -- so it is
                  intentionally a no-op here rather than a build error. */}
              {frame.event === 'action_proposal_created' &&
                `proposal created: ${frame.proposal.id}`}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-6">
        <AgentTopologyCanvas />
      </div>
    </div>
  )
}
