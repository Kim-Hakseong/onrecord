"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Header, Label, Notice, PageTitle, Shell } from "@/components/chrome";
import { VerdictBadge, VerdictCounts, evidenceFor } from "@/components/verdict";
import {
  getLedger,
  getMeta,
  type LedgerGroup,
  type LedgerResponse,
  type LedgerRow,
  type Meta,
  type VerdictName,
} from "@/lib/api";

function Row({ row }: { row: LedgerRow }) {
  const evidence = evidenceFor(row);
  return (
    <div
      className="row-hover grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 gap-y-1 border-t px-4 py-3 sm:grid-cols-[minmax(0,13rem)_7.5rem_minmax(0,1fr)_3rem] sm:items-center"
      style={{ borderColor: "var(--hairline)" }}
    >
      <span className="font-mono text-[13px]" style={{ color: "var(--ink)" }}>
        {row.field}
      </span>

      <span className="justify-self-end sm:justify-self-start">
        <VerdictBadge verdict={row.verdict} />
      </span>

      <span
        className="col-span-2 font-mono text-[13px] sm:col-span-1"
        style={{ color: row.value ? "var(--ink)" : "var(--ink-3)" }}
      >
        {row.value || "—"}
      </span>

      {row.call_id ? (
        <Link
          href={`/calls/${encodeURIComponent(row.call_id)}`}
          className="font-mono text-[11px] underline-offset-4 hover:underline"
          style={{ color: "var(--ink-3)" }}
        >
          {row.call_id.replace(/^call_onrecord_/, "#")}
        </Link>
      ) : (
        <span />
      )}

      {/* Every row carries its evidence. A row with none is a bug, not a style
          choice, so nothing is rendered rather than rendering an empty line. */}
      {evidence ? (
        <p
          className="col-span-2 text-[12px] leading-relaxed sm:col-span-4 sm:pl-1"
          style={{ color: "var(--ink-2)" }}
        >
          {evidence}
        </p>
      ) : null}
    </div>
  );
}

function Group({
  group,
  filter,
}: {
  group: LedgerGroup;
  filter: VerdictName | null;
}) {
  const rows = filter ? group.rows.filter((row) => row.verdict === filter) : group.rows;
  if (rows.length === 0) return null;
  return (
    <section className="panel lift overflow-hidden">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3.5">
        <span className="font-mono text-[14px] font-medium" style={{ color: "var(--ink)" }}>
          {group.subject_id}
        </span>
        {group.label ? (
          <span className="text-[13px]" style={{ color: "var(--ink-2)" }}>
            {group.label}
          </span>
        ) : null}
        {group.contact_org ? (
          <span className="text-[12px]" style={{ color: "var(--ink-3)" }}>
            {group.contact_org}
          </span>
        ) : null}
        <span className="ml-auto">
          <VerdictCounts counts={group.counts} compact />
        </span>
      </header>
      {rows.map((row) => (
        <Row key={`${row.subject_id}-${row.field}`} row={row} />
      ))}
    </section>
  );
}

export default function LedgerScreen() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [schema, setSchema] = useState<string>("supplier_delivery");
  const [ledger, setLedger] = useState<LedgerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Clicking a count chip narrows the ledger to that verdict. Real filtering of
  // data already on screen -- no request, nothing to wait for.
  const [filter, setFilter] = useState<VerdictName | null>(null);

  useEffect(() => {
    getMeta()
      .then((value) => {
        setMeta(value);
        if (!value.schemas.includes(schema) && value.schemas.length) {
          setSchema(value.schemas[0]);
        }
      })
      .catch((err) => setError(String(err)));
    // The schema selector drives the ledger fetch below, not this one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setLedger(null);
    setFilter(null);
    getLedger(schema)
      .then(setLedger)
      .catch((err) => setError(String(err)));
  }, [schema]);

  const open = ledger
    ? ledger.counts.UNRESOLVED + ledger.counts.NO_AUTHORITY
    : 0;

  return (
    <Shell>
      <Header meta={meta} schema={schema} onSchemaChange={setSchema} />

      <PageTitle
        eyebrow="Every field a call was supposed to settle"
        title={
          ledger
            ? open === 0
              ? "Nothing left open"
              : `${open} still open`
            : "Ledger"
        }
        aside={
          ledger ? (
            <div className="flex flex-col items-start gap-2 sm:items-end">
              <Label>
                {filter ? "filtered — click again to clear" : "across all subjects"}
              </Label>
              <VerdictCounts
                counts={ledger.counts}
                selected={filter}
                onSelect={setFilter}
              />
            </div>
          ) : null
        }
      />

      {error ? (
        <Notice tone="alert">
          {error}. Start the API with{" "}
          <code className="font-mono">uv run onrecord serve</code>.
        </Notice>
      ) : null}

      {ledger ? (
        <div className="space-y-3 px-4 sm:px-6">
          {ledger.groups.map((group) => (
            <Group key={group.subject_id} group={group} filter={filter} />
          ))}
        </div>
      ) : null}

      {ledger && filter && ledger.counts[filter] === 0 ? (
        <Notice>
          Nothing is {filter.toLowerCase().replace("_", " ")} in this pack right
          now. That is a fact about the ledger, not an empty screen.
        </Notice>
      ) : null}

      {ledger && ledger.groups.length === 0 ? (
        <Notice>
          Nothing recorded for this domain pack yet. Run{" "}
          <code className="font-mono">
            uv run onrecord --replay --schema schemas/{schema}.yaml --db
            data/onrecord.db
          </code>
          .
        </Notice>
      ) : null}
    </Shell>
  );
}
