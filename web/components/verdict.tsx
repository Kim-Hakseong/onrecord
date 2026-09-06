import type { LedgerRow, RuleStep, VerdictName } from "@/lib/api";

/** Surface and foreground are separate on purpose: the pastel tint is never
 *  used for text, so every badge clears contrast in both themes. */
const TINT: Record<VerdictName, string> = {
  CONFIRMED: "var(--confirmed-bg)",
  CONTRADICTED: "var(--contradicted-bg)",
  UNRESOLVED: "var(--unresolved-bg)",
  NO_AUTHORITY: "var(--noauthority-bg)",
};

const FG: Record<VerdictName, string> = {
  CONFIRMED: "var(--confirmed-fg)",
  CONTRADICTED: "var(--contradicted-fg)",
  UNRESOLVED: "var(--unresolved-fg)",
  NO_AUTHORITY: "var(--noauthority-fg)",
};

export const verdictColor = (verdict: VerdictName) => FG[verdict];
export const verdictTint = (verdict: VerdictName) => TINT[verdict];

export const VERDICTS: VerdictName[] = [
  "CONFIRMED",
  "CONTRADICTED",
  "UNRESOLVED",
  "NO_AUTHORITY",
];

const LABEL: Record<VerdictName, string> = {
  CONFIRMED: "Confirmed",
  CONTRADICTED: "Contradicted",
  UNRESOLVED: "Unresolved",
  NO_AUTHORITY: "No authority",
};

/** Tint plus the word, always. Nothing here is distinguished by hue alone. */
export function VerdictBadge({
  verdict,
  size = "md",
}: {
  verdict: VerdictName;
  size?: "sm" | "md";
}) {
  return (
    <span
      className={`pill inline-flex shrink-0 items-center font-medium ${
        size === "sm" ? "px-2 py-[1px] text-[11px]" : "px-2.5 py-[3px] text-[12px]"
      }`}
      style={{ background: TINT[verdict], color: FG[verdict] }}
    >
      {LABEL[verdict]}
    </span>
  );
}

export function VerdictCounts({
  counts,
  compact = false,
}: {
  counts: Record<VerdictName, number>;
  compact?: boolean;
}) {
  return (
    <div className={`flex flex-wrap items-center ${compact ? "gap-2" : "gap-2.5"}`}>
      {/* All four appear even at zero. They are equal first-class states, and a
          zero is itself a fact about the ledger. */}
      {VERDICTS.map((verdict) => {
        const value = counts?.[verdict] ?? 0;
        return (
          <span
            key={verdict}
            className={`pill inline-flex items-center gap-1.5 ${
              compact ? "px-2 py-[2px]" : "px-3 py-1"
            }`}
            style={{
              background: TINT[verdict],
              color: FG[verdict],
              opacity: value === 0 ? 0.55 : 1,
            }}
          >
            <span className="font-mono text-[13px] font-medium tabular-nums">
              {value}
            </span>
            <span className={compact ? "text-[11px]" : "text-[12px]"}>
              {LABEL[verdict]}
            </span>
          </span>
        );
      })}
    </div>
  );
}

const MARK = { passed: "✓", failed: "✕", not_reached: "–" } as const;

export function RuleTrace({ row }: { row: LedgerRow }) {
  // Five rows, always. A four-row trace would be hiding the rule that decided.
  if (row.rule_trace.length !== 5) {
    return (
      <p className="font-mono text-[12px]" style={{ color: FG.CONTRADICTED }}>
        rule trace incomplete ({row.rule_trace.length}/5) — not rendering
      </p>
    );
  }
  return (
    <ol className="space-y-[3px]">
      {row.rule_trace.map((step: RuleStep) => {
        const reached = step.status !== "not_reached";
        const color = step.decided
          ? FG[row.verdict]
          : reached
            ? "var(--ink-2)"
            : "var(--ink-3)";
        return (
          <li
            key={step.index}
            className="flex items-baseline gap-2.5 rounded-lg px-2 py-[3px]"
            style={{
              background: step.decided ? TINT[row.verdict] : "transparent",
            }}
          >
            <span
              className="font-mono text-[11px] tabular-nums"
              style={{ color: "var(--ink-3)" }}
            >
              {step.index}
            </span>
            <span
              className="w-[68px] shrink-0 font-mono text-[12px]"
              style={{ color }}
            >
              {step.rule}
            </span>
            <span
              className="w-3 shrink-0 text-center text-[12px]"
              style={{ color }}
              aria-hidden="true"
            >
              {MARK[step.status]}
            </span>
            <span className="text-[12px] leading-snug" style={{ color: "var(--ink-2)" }}>
              {/* The deciding rule says so in words; the rest stay quiet. */}
              {step.decided && !step.detail
                ? "decided here"
                : step.detail}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** The evidence line under a ledger row. A row with no evidence is not rendered. */
export function evidenceFor(row: LedgerRow): string | null {
  if (row.verdict === "CONTRADICTED") {
    return `was ${row.known_value || "—"} on record`;
  }
  if (row.verdict === "CONFIRMED") {
    return row.quote ? `“${row.quote}”` : null;
  }
  if (row.verdict === "NO_AUTHORITY") {
    return `answered by ${row.respondent_role} — not on the authority list`;
  }
  return row.reason_text || null;
}
