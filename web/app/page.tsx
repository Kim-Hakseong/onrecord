"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Empty, Header, Shell } from "@/components/chrome";
import { VerdictBadge, VerdictCounts, evidenceFor } from "@/components/verdict";
import {
  getLedger,
  getMeta,
  type LedgerResponse,
  type Meta,
} from "@/lib/api";

export default function LedgerScreen() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [schema, setSchema] = useState<string>("supplier_delivery");
  const [ledger, setLedger] = useState<LedgerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMeta()
      .then((value) => {
        setMeta(value);
        if (!value.schemas.includes(schema) && value.schemas.length) {
          setSchema(value.schemas[0]);
        }
      })
      .catch((err) => setError(String(err)));
    // The schema selector re-runs the ledger fetch below, not this one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setLedger(null);
    getLedger(schema)
      .then(setLedger)
      .catch((err) => setError(String(err)));
  }, [schema]);

  return (
    <Shell>
      <Header meta={meta} schema={schema} onSchemaChange={setSchema} />
      {error ? (
        <Empty>
          {error}. Start the API with{" "}
          <code className="font-mono">uv run onrecord serve</code>.
        </Empty>
      ) : null}

      {ledger ? (
        <>
          <VerdictCounts counts={ledger.counts} />
          <table className="w-full">
            <thead>
              <tr className="text-left font-mono text-[11px] uppercase tracking-[0.06em] text-[var(--color-text-3)]">
                <th className="px-4 py-2 font-medium">subject</th>
                <th className="px-4 py-2 font-medium">field</th>
                <th className="px-4 py-2 font-medium">verdict</th>
                <th className="px-4 py-2 font-medium">value</th>
                <th className="px-4 py-2 font-medium">call</th>
              </tr>
            </thead>
            <tbody>
              {ledger.rows.map((row) => {
                const evidence = evidenceFor(row);
                return (
                  <tr
                    key={`${row.subject_id}-${row.field}`}
                    className="border-t border-[var(--color-border)] align-top hover:bg-[var(--color-surface-2)]"
                  >
                    <td className="px-4 py-3 font-mono text-[13px]">
                      {row.subject_id}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-mono text-[13px]">{row.field}</div>
                      {/* Every row carries its evidence. A row with none is a bug. */}
                      {evidence ? (
                        <div className="mt-1 pl-3 text-[12px] text-[var(--color-text-2)]">
                          ▸ {evidence}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      <VerdictBadge verdict={row.verdict} />
                    </td>
                    <td className="px-4 py-3 font-mono text-[13px]">
                      {row.value || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {row.call_id ? (
                        <Link
                          href={`/calls/${encodeURIComponent(row.call_id)}`}
                          className="font-mono text-[12px] text-[var(--color-dial)]"
                        >
                          {row.call_id}
                        </Link>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {ledger.rows.length === 0 ? (
            <Empty>
              Nothing recorded for this domain pack yet. Run{" "}
              <code className="font-mono">
                uv run onrecord --replay --schema schemas/{schema}.yaml --db
                data/onrecord.db
              </code>
              .
            </Empty>
          ) : null}
        </>
      ) : null}
    </Shell>
  );
}
