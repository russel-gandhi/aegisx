// Bible Section 15 (Limitations) treats this banner as a stated compliance control, not
// decoration: every screen must carry it, unmodified, for as long as the app runs on
// synthetic demo data. Reproduced character-for-character from Bible line 1374, em dashes
// included — do not paraphrase or reformat this string.
export default function PrototypeBanner() {
  return (
    <div
      role="alert"
      className="w-full bg-red-600 px-4 py-2 text-center text-sm font-semibold tracking-wide text-white"
    >
      PROTOTYPE — SYNTHETIC DATA — NOT VALIDATED FOR PRODUCTION GxP USE
    </div>
  )
}
