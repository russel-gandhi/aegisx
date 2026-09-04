// Bible Section 15 (Limitations) treats this banner as a stated compliance control, not
// decoration: every screen must carry it, unmodified, for as long as the app runs on
// synthetic demo data. Reproduced character-for-character from Bible line 1374, em dashes
// included — do not paraphrase or reformat this string.
//
// Styled with the same soft-color language every other alert/error surface in the app
// uses (bg-red-soft + text-red, see EvidenceView's insufficient-evidence panel) rather
// than a solid full-bleed red block -- a compliance notice that reads as "part of this
// product's design system" instead of a one-off browser-alarm color clashing with it.
export default function PrototypeBanner() {
  return (
    <div
      role="alert"
      className="relative z-30 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-b border-red-500/25 bg-red-soft px-4 py-1.5 text-center text-[12px] font-semibold tracking-wide text-red sm:text-[13px]"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-3.5 w-3.5 shrink-0"
      >
        <path
          fillRule="evenodd"
          d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 6a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
          clipRule="evenodd"
        />
      </svg>
      <span>PROTOTYPE — SYNTHETIC DATA — NOT VALIDATED FOR PRODUCTION GxP USE</span>
    </div>
  )
}
