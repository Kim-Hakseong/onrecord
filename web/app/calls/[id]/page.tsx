"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { Header, Label, Notice, PageTitle, Shell } from "@/components/chrome";
import { RuleTrace, VerdictBadge, verdictTint } from "@/components/verdict";
import {
  getCall,
  getMeta,
  type CallDetail,
  type Meta,
  type TranscriptLine,
} from "@/lib/api";

const SPEAKER_LABEL: Record<string, string> = {
  agent: "agent",
  callee: "them",
  unknown: "—",
};

/** One line per turn, with the confirmed spans highlighted where they were
 *  actually said. The segments come from the API, which cut them against the
 *  adjudicator's own offsets — so what is highlighted is exactly what the
 *  verdict rests on, not a second search over the text.
 *
 *  Each highlight is a real button: the sentence and the verdict it produced
 *  are two views of one fact, so the screen lets you move between them. */
function Transcript({
  lines,
  active,
  onHover,
  onPick,
}: {
  lines: TranscriptLine[];
  active: string | null;
  onHover: (field: string | null) => void;
  onPick: (field: string) => void;
}) {
  return (
    <div className="space-y-2.5">
      {lines.map((line, index) => {
        const isAgent = line.speaker === "agent";
        return (
          <div key={index} className="grid grid-cols-[3.25rem_minmax(0,1fr)] gap-3">
            <span
              className="pt-[2px] text-right font-mono text-[11px]"
              style={{ color: "var(--ink-3)" }}
            >
              {SPEAKER_LABEL[line.speaker] ?? line.speaker}
            </span>
            <p
              className="font-mono text-[13px] leading-relaxed"
              style={{ color: isAgent ? "var(--ink-2)" : "var(--ink)" }}
            >
              {line.segments.map((piece, pieceIndex) =>
                piece.field ? (
                  <button
                    type="button"
                    key={pieceIndex}
                    className="quote"
                    data-active={active === piece.field}
                    title={`Evidence for ${piece.field} — click to jump to its verdict`}
                    onMouseEnter={() => onHover(piece.field)}
                    onMouseLeave={() => onHover(null)}
                    onFocus={() => onHover(piece.field)}
                    onBlur={() => onHover(null)}
                    onClick={() => onPick(piece.field!)}
                  >
                    {piece.text}
                  </button>
                ) : (
                  <span key={pieceIndex}>{piece.text}</span>
                ),
              )}
            </p>
          </div>
        );
      })}
    </div>
  );
}

export default function CallDetailScreen({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [detail, setDetail] = useState<CallDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [landed, setLanded] = useState<string | null>(null);
  const cards = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    getMeta().then(setMeta).catch(() => undefined);
    getCall(id)
      .then(setDetail)
      .catch((err) => setError(String(err)));
  }, [id]);

  /** Jump to the verdict a quoted sentence produced, and mark where you landed. */
  const jumpTo = useCallback((field: string) => {
    const card = cards.current[field];
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    setLanded(field);
    window.setTimeout(() => setLanded((f) => (f === field ? null : f)), 800);
  }, []);

  const settled = detail
    ? detail.counts.CONFIRMED + detail.counts.CONTRADICTED
    : 0;

  return (
    <Shell>
      <Header meta={meta} />

      <PageTitle
        eyebrow={
          detail
            ? `${detail.call.subject_id} · attempt ${detail.call.attempt} · ${detail.call.duration_seconds}s`
            : "Call"
        }
        title={
          detail
            ? settled === 0
              ? "This call settled nothing"
              : `${settled} of ${detail.rows.length} settled`
            : "Call detail"
        }
        aside={
          detail ? (
            <Link
              href="/"
              className="pill lift px-4 py-2 text-[13px]"
              style={{
                background: "var(--surface-solid)",
                color: "var(--ink-2)",
                boxShadow: "var(--shadow-float)",
              }}
            >
              ← Ledger
            </Link>
          ) : null
        }
      />

      {error ? <Notice tone="alert">{error}</Notice> : null}

      {detail ? (
        <div className="grid grid-cols-1 items-start gap-3 px-4 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="panel p-5 lg:sticky lg:top-24">
            <div className="mb-4 flex items-center justify-between gap-3">
              <Label>transcript</Label>
              <span
                className="font-mono text-[11px]"
                style={{ color: "var(--ink-3)" }}
              >
                {detail.call.mode}
                {detail.call.end_reason ? ` · ${detail.call.end_reason}` : ""}
              </span>
            </div>

            <Transcript
              lines={detail.lines}
              active={active}
              onHover={setActive}
              onPick={jumpTo}
            />

            <div
              className="mt-5 flex flex-wrap gap-x-4 gap-y-1 border-t pt-4 font-mono text-[11px]"
              style={{ borderColor: "var(--hairline)", color: "var(--ink-3)" }}
            >
              <span>{detail.call.id}</span>
              {/* The duration is on screen because "the follow-up call is
                  shorter" is a numeric claim and should be checkable. */}
              <span>{detail.call.duration_seconds}s</span>
              <span>respondent: {detail.call.respondent_role}</span>
            </div>
          </section>

          <section className="space-y-3">
            {detail.rows.map((row) => {
              const linked = row.quote_start >= 0;
              return (
                <article
                  key={row.field}
                  ref={(node) => {
                    cards.current[row.field] = node;
                  }}
                  className={`panel overflow-hidden ${landed === row.field ? "settled" : ""}`}
                  style={{
                    boxShadow:
                      active === row.field ? "var(--shadow-lift)" : undefined,
                  }}
                  onMouseEnter={() => linked && setActive(row.field)}
                  onMouseLeave={() => linked && setActive(null)}
                >
                  <header
                    className="flex flex-wrap items-center gap-3 px-5 py-3.5"
                    style={{ background: verdictTint(row.verdict) }}
                  >
                    <span
                      className="font-mono text-[13px] font-medium"
                      style={{ color: "var(--ink)" }}
                    >
                      {row.field}
                    </span>
                    <VerdictBadge verdict={row.verdict} size="sm" />
                    <span
                      className="ml-auto font-mono text-[13px]"
                      style={{ color: row.value ? "var(--ink)" : "var(--ink-3)" }}
                    >
                      {row.value || "—"}
                    </span>
                  </header>
                  <div className="px-3 py-3">
                    <RuleTrace row={row} />
                  </div>
                  {row.verdict === "CONTRADICTED" ? (
                    <p
                      className="px-5 pb-4 text-[12px]"
                      style={{ color: "var(--ink-2)" }}
                    >
                      Our record said{" "}
                      <span className="font-mono">{row.known_value}</span>.
                    </p>
                  ) : null}
                </article>
              );
            })}

            {detail.rejected_spans.length ? (
              <article className="panel p-5">
                <Label>spans rejected</Label>
                <div className="mt-3 space-y-2">
                  {detail.rejected_spans.map((span) => (
                    <p
                      key={span.field}
                      className="text-[12px] leading-relaxed"
                      style={{ color: "var(--ink-2)" }}
                    >
                      <span className="font-mono">{span.field}</span>: the{" "}
                      {span.source} offered{" "}
                      <span className="font-mono">{span.claimed_value}</span>,
                      citing{" "}
                      <span className="font-mono">“{span.claimed_quote}”</span> —
                      {" "}
                      {span.detail}. There is nothing to highlight on the left,
                      which is the point.
                    </p>
                  ))}
                </div>
              </article>
            ) : null}
          </section>
        </div>
      ) : null}
    </Shell>
  );
}
