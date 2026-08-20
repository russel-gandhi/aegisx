export default function Actions() {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Action / Approval Centre</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        Every GxP-relevant write proposed by A7 Remediation sits here PENDING until a human
        approves it. Approval dialogs render exclusively from server-trusted proposal metadata,
        never from LLM-generated markup.
      </p>
    </div>
  )
}
