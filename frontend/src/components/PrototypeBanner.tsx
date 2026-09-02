// Bible Section 15 (Limitations) treats this banner as a stated compliance control, not
// decoration: every screen must carry it, unmodified, for as long as the app runs on
// synthetic demo data. Reproduced character-for-character from Bible line 1374, em dashes
// included — do not paraphrase or reformat this string.
export default function PrototypeBanner() {
  return (
    <div
      role="alert"
      className="relative z-30 flex items-center justify-center gap-2 border-b border-red-500/30 bg-gradient-to-r from-red-600 via-red-500 to-red-600 px-4 py-2 text-center text-[13px] font-semibold tracking-wide text-white shadow-[0_1px_0_rgba(255,255,255,0.15)_inset]"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-3.5 w-3.5 shrink-0 opacity-90"
      >
        <path
          fillRule="evenodd"
          d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 6a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
          clipRule="evenodd"
        />
      </svg>
      PROTOTYPE — SYNTHETIC DATA — NOT VALIDATED FOR PRODUCTION GxP USE
    </div>
  )
}
