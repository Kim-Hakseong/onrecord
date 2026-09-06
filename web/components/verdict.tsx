import type { LedgerRow, RuleStep, VerdictName } from "@/lib/api";

const COLOR: Record<VerdictName, string> = {
  CONFIRMED: "var(--color-confirmed)",
  CONTRADICTED: "var(--color-contradicted)",
  UNRESOLVED: "var(--color-unresolved)",
  NO_AUTHORITY: "var(--color-noauthority)",
};

const TINT: Record<VerdictName, string> = {
  CONFIRMED: "rgba(52,211,153,0.12)",
  CONTRADICTED: "rgba(248,113,113,0.12)",
  UNRESOLVED: "rgba(251,191,36,0.12)",
  NO_AUTHORITY: "rgba(167,139,250,0.12)",
};

export const VERDICTS: VerdictName[] = [
  "CONFIRMED",
  "CONTRADICTED",
  "UNRESOLVED",
  "NO_AUTHORITY",
];

/** Colour plus the word, always. Nothing in this UI is distinguished by hue alone. */
export function VerdictBadge({ verdict }: { verdict: VerdictName }) {
  return (
    <span
      className="inline-block rounded-[4px] border px-2 py-[2px] font-mono text-[11px] font-medium uppercase tracking-[0.06em]"
      style={{
        color: COLOR[verdict],
        borderColor: COLOR[verdict],
        background: TINT[verdict],
      }}
    >
      {verdict}
    </span>
  );
}

export function VerdictCounts({
  counts,
}: {
  counts: Record<VerdictName, number>;
}) {
  return (
    <div className="flex flex-wrap items-center gap-6 border-b border-[var(--color-border)] px-4 py-3">
      {/* All four are shown even at zero: they are equal first-class states. */}
      {VERDICTS.map((verdict) => (
        <span key={verdict} className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: COLOR[verdict] }}
          />
          <span className="font-mono text-[13px]">{counts?.[verdict] ?? 0}</span>
          <span className="font-mono text-[11px] uppercase tracking-[0.06em] text-[var(--color-text-2)]">
            {verdict}
          </span>
        </span>
      ))}
    </div>
  );
}

const SYMBOL = { passed: "✓", failed: "✕", not_reached: "—" } as const;

export function RuleTrace({ row }: { row: LedgerRow }) {
  // Five rows, always. A four-row trace would be hiding the rule that decided.
  if (row.rule_trace.length !== 5) {
    return (
      <p className="font-mono text-[12px] text-[var(--color-contradicted)]">
        rule trace incomplete ({row.rule_trace.length}/5) — not rendering
      </p>
    );
  }
  return (
    <ul className="space-y-1">
      {row.rule_trace.map((step: RuleStep) => (
        <li key={step.index} className="flex gap-3 font-mono text-[12px]">
          <span className="text-[var(--color-text-3)]">
            {"①②③④⑤"[step.index - 1]}
          </span>
          <span className="w-20 text-[var(--color-text-2)]">{step.rule}</span>
          <span
            style={{
              color:
                step.status === "failed"
                  ? COLOR[row.verdict]
                  : step.status === "passed"
                    ? "var(--color-text)"
                    : "var(--color-text-3)",
            }}
          >
            {SYMBOL[step.status]}
          </span>
          <span className="text-[var(--color-text-2)]">{step.detail}</span>
        </li>
      ))}
    </ul>
  );
}

/** The evidence line under a ledger row. A row with no evidence is not rendered. */
export function evidenceFor(row: LedgerRow): string | null {
  if (row.verdict === "CONTRADICTED") {
    return `was ${row.known_value || "—"} on record`;
  }
  if (row.verdict === "CONFIRMED") {
    return row.quote ? `"${row.quote}"` : null;
  }
  if (row.verdict === "NO_AUTHORITY") {
    return `answered by ${row.respondent_role} — not on the authority list`;
  }
  return row.reason_text || null;
}
