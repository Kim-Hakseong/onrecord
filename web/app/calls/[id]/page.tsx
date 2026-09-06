"use client";

import { use, useEffect, useState } from "react";
import { Empty, Header, Shell } from "@/components/chrome";
import { RuleTrace, VerdictBadge } from "@/components/verdict";
import { getCall, getMeta, type CallDetail, type Meta } from "@/lib/api";

/** Renders the transcript with the confirmed spans highlighted in place.
 *  The offsets come from the adjudicator, so what is highlighted is exactly
 *  what the verdict was based on -- not a re-search of the text. */
function Transcript({ detail }: { detail: CallDetail }) {
  const text = detail.call.transcript;
  const spans = detail.rows
    .filter((row) => row.quote_start >= 0)
    .map((row) => ({ start: row.quote_start, end: row.quote_end, field: row.field }))
    .sort((a, b) => a.start - b.start);

  const pieces: React.ReactNode[] = [];
  let cursor = 0;
  spans.forEach((span, index) => {
    if (span.start < cursor) return; // overlapping spans: keep the first
    pieces.push(<span key={`t${index}`}>{text.slice(cursor, span.start)}</span>);
    pieces.push(
      <mark className="quote" key={`q${index}`} title={span.field}>
        {text.slice(span.start, span.end)}
      </mark>,
    );
    cursor = span.end;
  });
  pieces.push(<span key="tail">{text.slice(cursor)}</span>);

  return (
    <pre className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed">
      {pieces}
    </pre>
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

  useEffect(() => {
    getMeta().then(setMeta).catch(() => undefined);
    getCall(id)
      .then(setDetail)
      .catch((err) => setError(String(err)));
  }, [id]);

  return (
    <Shell>
      <Header meta={meta} />
      {error ? <Empty>{error}</Empty> : null}
      {detail ? (
        <div className="grid grid-cols-1 gap-3 p-4 lg:grid-cols-2">
          <section className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-4">
            <h2 className="mb-3 font-mono text-[11px] uppercase tracking-[0.06em] text-[var(--color-text-2)]">
              transcript
            </h2>
            <Transcript detail={detail} />
            <p className="mt-4 font-mono text-[12px] text-[var(--color-text-3)]">
              {/* The duration is on screen because the shrinking-call claim is
                  a numeric one and should be checkable. */}
              call {detail.call.id} · attempt {detail.call.attempt} ·{" "}
              {detail.call.duration_seconds}s · {detail.call.mode}
              {detail.call.end_reason ? ` · ${detail.call.end_reason}` : ""}
            </p>
            <p className="font-mono text-[12px] text-[var(--color-text-3)]">
              respondent: {detail.call.respondent_role}
            </p>
          </section>

          <section className="space-y-3">
            {detail.rows.map((row) => (
              <div
                key={row.field}
                className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-4"
              >
                <div className="mb-3 flex items-center gap-3">
                  <span className="font-mono text-[13px]">{row.field}</span>
                  <VerdictBadge verdict={row.verdict} />
                  <span className="ml-auto font-mono text-[13px]">
                    {row.value || "—"}
                  </span>
                </div>
                <RuleTrace row={row} />
              </div>
            ))}

            {detail.rejected_spans.length ? (
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                <h3 className="mb-2 font-mono text-[11px] uppercase tracking-[0.06em] text-[var(--color-text-2)]">
                  spans rejected
                </h3>
                {detail.rejected_spans.map((span) => (
                  <p
                    key={span.field}
                    className="font-mono text-[12px] text-[var(--color-text-2)]"
                  >
                    {span.field}: “{span.claimed_quote}” {span.detail} → value{" "}
                    {span.claimed_value} discarded ({span.source})
                  </p>
                ))}
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </Shell>
  );
}
