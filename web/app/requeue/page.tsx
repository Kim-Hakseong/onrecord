"use client";

import { useEffect, useState } from "react";
import { Header, Label, Notice, PageTitle, Shell } from "@/components/chrome";
import { VerdictBadge } from "@/components/verdict";
import {
  getMeta,
  getRequeue,
  runRequeue,
  type Meta,
  type RequeueCard,
} from "@/lib/api";

/** The goal is shown verbatim, never summarised — but it is long enough to bury
 *  the card, so it collapses to its first line until asked for. */
function NextGoal({ card }: { card: RequeueCard }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const questions = card.next_fields.length;

  async function copy() {
    try {
      await navigator.clipboard.writeText(card.next_goal);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the text is on screen under "show" anyway */
    }
  }
  return (
    <div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="flex items-center gap-2 text-left"
        >
          <Label>
            next goal · {questions} {questions === 1 ? "question" : "questions"}
          </Label>
          <span className="text-[11px]" style={{ color: "var(--ink-3)" }}>
            {open ? "hide" : "show"}
          </span>
        </button>
        {open ? (
          <button
            type="button"
            onClick={copy}
            className="pill px-2.5 py-1 text-[11px]"
            style={{ background: "var(--surface-sunken)", color: "var(--ink-2)" }}
          >
            {copied ? "copied" : "copy"}
          </button>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {card.next_fields.map((field) => (
          <span
            key={field}
            className="pill px-2.5 py-1 font-mono text-[12px]"
            style={{ background: "var(--surface-sunken)", color: "var(--ink-2)" }}
          >
            {field}
          </span>
        ))}
      </div>

      {open ? (
        <pre
          className="sunken scroll-soft mt-3 max-h-56 overflow-auto whitespace-pre-wrap p-4 font-mono text-[12px] leading-relaxed"
          style={{ color: "var(--ink-2)" }}
        >
          {card.next_goal}
        </pre>
      ) : null}
    </div>
  );
}

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

  const actionable = cards?.filter((card) => card.actionable).length ?? 0;

  return (
    <Shell>
      <Header meta={meta} />

      <PageTitle
        eyebrow="Fields waiting on another call"
        title={cards ? `${actionable} ready to redial` : "Requeue"}
      />

      {error ? <Notice tone="alert">{error}</Notice> : null}

      <div className="space-y-3 px-4 sm:px-6">
        {cards?.map((card) => {
          const exhausted = !card.actionable;
          return (
            <article
              key={card.subject_id}
              className="panel lift p-5"
              style={{ opacity: exhausted ? 0.62 : 1 }}
            >
              <header className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span
                  className="font-mono text-[14px] font-medium"
                  style={{ color: "var(--ink)" }}
                >
                  {card.subject_id}
                </span>
                <span className="text-[13px]" style={{ color: "var(--ink-2)" }}>
                  {card.label}
                </span>
                <span
                  className="pill ml-auto px-2.5 py-1 font-mono text-[11px]"
                  style={{
                    background: "var(--surface-sunken)",
                    color: exhausted ? "var(--contradicted-fg)" : "var(--ink-3)",
                  }}
                >
                  attempt {card.attempts} of {card.max_attempts}
                  {exhausted ? " · exhausted" : ""}
                </span>
              </header>

              <div className="mt-5 grid gap-5 lg:grid-cols-2">
                <div>
                  <Label>still open</Label>
                  <div className="mt-2 space-y-1.5">
                    {card.open.map((item) => (
                      <div key={item.field} className="flex flex-wrap items-center gap-2">
                        <span
                          className="font-mono text-[13px]"
                          style={{ color: "var(--ink)" }}
                        >
                          {item.field}
                        </span>
                        <VerdictBadge verdict={item.verdict} size="sm" />
                        {item.needs_different_respondent ? (
                          <span
                            className="text-[12px]"
                            style={{ color: "var(--ink-3)" }}
                          >
                            needs a different respondent
                          </span>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>

                {/* This block is the point of the screen: visible proof that the
                    follow-up will not ask again about anything already settled. */}
                {card.dropped_from_goal.length ? (
                  <div>
                    <Label>dropped from goal</Label>
                    <div className="mt-2 space-y-1.5">
                      {card.dropped_from_goal.map((item) => (
                        <div key={item.field} className="flex flex-wrap items-center gap-2">
                          <span
                            className="font-mono text-[13px]"
                            style={{ color: "var(--ink-3)" }}
                          >
                            {item.field}
                          </span>
                          <VerdictBadge verdict={item.verdict} size="sm" />
                          <span
                            className="font-mono text-[12px]"
                            style={{ color: "var(--ink-3)" }}
                          >
                            {item.value || "—"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="mt-5">
                <NextGoal card={card} />
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={exhausted || budgetHeld || busy !== null}
                  onClick={() => callAgain(card)}
                  title={
                    budgetHeld
                      ? "call budget reserved for demo"
                      : exhausted
                        ? "no attempts left"
                        : "places a real call and spends call budget"
                  }
                  className="pill lift px-5 py-2.5 text-[13px] font-medium disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0"
                  style={{
                    background: "var(--accent)",
                    color: "var(--accent-ink)",
                    boxShadow: "var(--shadow-float)",
                  }}
                >
                  {busy === card.subject_id ? "calling…" : "Call again →"}
                </button>
                {budgetHeld ? (
                  <span
                    className="text-[12px]"
                    style={{ color: "var(--unresolved-fg)" }}
                  >
                    call budget reserved for demo
                  </span>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>

      {cards && cards.length === 0 ? (
        <Notice>Nothing is waiting on another call.</Notice>
      ) : null}
    </Shell>
  );
}
