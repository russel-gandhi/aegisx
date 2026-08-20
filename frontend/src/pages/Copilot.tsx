import AgentTopologyCanvas from '../components/AgentTopologyCanvas'

export default function Copilot() {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Ask GxP Copilot</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        A natural-language chat interface backed by the C2 → A0 → [A1…A6] → C1 → A7 → C3 agent
        pipeline. The canvas below visualizes live agent execution state as a question moves
        through orchestration, evidence verification, and remediation.
      </p>
      <div className="mt-6">
        <AgentTopologyCanvas />
      </div>
    </div>
  )
}
