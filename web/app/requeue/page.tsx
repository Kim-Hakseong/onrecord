"use client";

import { useEffect, useState } from "react";
import { Empty, Header, Shell } from "@/components/chrome";
import { VerdictBadge } from "@/components/verdict";
import {
  getMeta,
  getRequeue,
  runRequeue,
  type Meta,
  type RequeueCard,
} from "@/lib/api";

export default function RequeueScreen() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [cards, setCards] = useState<RequeueCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    getMeta().then(setMeta).catch(() => undefined);
    getRequeue()
      .then(setCards)
      .catch((err) => setError(String(err)));
  };

  useEffect(load, []);

  const budgetHeld =
    meta !== null && meta.calls_remaining <= meta.live_call_floor;

  async function callAgain(card: RequeueCard) {
    setBusy(card.subject_id);
    setError(null);
    try {
      await runRequeue(card.subject_id, card.schema_name);
      load();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Shell>
      <Header meta={meta} />
      {error ? <Empty>{error}</Empty> : null}

      <h1 className="px-4 pt-4 text-[20px] font-semibold tracking-[-0.01em]">
        Requeue ({cards?.length ?? 0})
      </h1>

      <div className="space-y-3 p-4">
        {cards?.map((card) => (
          <article
            key={card.subject_id}
            className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-4"
            style={{ opacity: card.actionable ? 1 : 0.55 }}
          >
            <div className="flex items-center gap-3">
              <span className="font-mono text-[13px]">{card.subject_id}</span>
              <span className="text-[12px] text-[var(--color-text-3)]">
                {card.label}
              </span>
              <span className="ml-auto font-mono text-[12px] text-[var(--color-text-3)]">
                attempt {card.attempts} of {card.max_attempts}
                {card.actionable ? "" : " · EXHAUSTED"}
              </span>
            </div>

            <div className="mt-3">
              <h3 className="font-mono text-[11px] uppercase tracking-[0.06em] text-[var(--color-text-2)]">
                still open
              </h3>
              {card.open.map((item) => (
                <div key={item.field} className="mt-1 flex items-center gap-3">
                  <span className="font-mono text-[13px]">{item.field}</span>
                  <VerdictBadge verdict={item.verdict} />
                  {item.needs_different_respondent ? (
                    <span className="text-[12px] text-[var(--color-text-2)]">
                      needs a different respondent
                    </span>
                  ) : null}
                </div>
              ))}
            </div>

            {/* This block is the point of the screen: proof that the follow-up
                call will not ask again about anything already settled. */}
            {card.dropped_from_goal.length ? (
              <div className="mt-3">
                <h3 className="font-mono text-[11px] uppercase tracking-[0.06em] text-[var(--color-text-2)]">
                  dropped from goal
                </h3>
                {card.dropped_from_goal.map((item) => (
                  <div key={item.field} className="mt-1 flex items-center gap-3">
                    <span className="font-mono text-[13px] text-[var(--color-text-2)]">
                      {item.field}
                    </span>
                    <VerdictBadge verdict={item.verdict} />
                    <span className="font-mono text-[13px] text-[var(--color-text-2)]">
                      {item.value || "—"}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="mt-3">
              <h3 className="font-mono text-[11px] uppercase tracking-[0.06em] text-[var(--color-text-2)]">
                next goal ({card.next_fields.length}{" "}
                {card.next_fields.length === 1 ? "question" : "questions"})
              </h3>
              {/* The exact text CALL-E will be given. Not a summary of it. */}
              <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded-[4px] bg-[var(--color-surface-2)] p-3 font-mono text-[12px] text-[var(--color-text-2)]">
                {card.next_goal}
              </pre>
            </div>

            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                disabled={!card.actionable || budgetHeld || busy !== null}
                onClick={() => callAgain(card)}
                title={
                  budgetHeld
                    ? "call budget reserved for demo"
                    : card.actionable
                      ? "places a real call"
                      : "no attempts left"
                }
                className="rounded-md px-4 py-2 font-mono text-[12px] disabled:cursor-not-allowed disabled:opacity-40"
                style={{ background: "var(--color-dial)", color: "#08131a" }}
              >
                {busy === card.subject_id ? "calling…" : "Call again →"}
              </button>
              {budgetHeld ? (
                <span className="text-[12px] text-[var(--color-unresolved)]">
                  call budget reserved for demo
                </span>
              ) : null}
            </div>
          </article>
        ))}
      </div>

      {cards && cards.length === 0 ? (
        <Empty>Nothing is waiting on another call.</Empty>
      ) : null}
    </Shell>
  );
}
