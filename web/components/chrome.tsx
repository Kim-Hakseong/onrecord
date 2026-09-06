"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Meta } from "@/lib/api";

/** Two entries, three screens: call detail is reached by clicking a ledger row.
 *  There is no fourth screen and no settings page. */
const SCREENS = [
  { href: "/", label: "Ledger" },
  { href: "/requeue", label: "Requeue" },
];

/** `Calls 13 / 20`, top right, on every screen. The budget is part of the design. */
export function CallCounter({ meta }: { meta: Meta | null }) {
  if (!meta) return null;
  const remaining = meta.calls_remaining;
  const color =
    remaining <= meta.live_call_floor
      ? "var(--color-contradicted)"
      : remaining <= 5
        ? "var(--color-unresolved)"
        : "var(--color-text-2)";
  return (
    <span className="font-mono text-[12px] font-medium" style={{ color }}>
      Calls {meta.calls_used} / {meta.call_budget}
    </span>
  );
}

export function Header({
  meta,
  schema,
  onSchemaChange,
}: {
  meta: Meta | null;
  schema?: string;
  onSchemaChange?: (schema: string) => void;
}) {
  const pathname = usePathname();
  return (
    <header className="flex h-14 items-center gap-6 border-b border-[var(--color-border)] px-4">
      <Link href="/" className="font-mono text-[13px] font-medium tracking-[0.08em]">
        ONRECORD
      </Link>

      <nav className="flex gap-4">
        {SCREENS.map((screen) => {
          const active =
            screen.href === "/"
              ? pathname === "/"
              : pathname.startsWith(screen.href);
          return (
            <Link
              key={screen.href}
              href={screen.href}
              className="text-[13px]"
              style={{
                color: active ? "var(--color-text)" : "var(--color-text-3)",
              }}
            >
              {screen.label}
            </Link>
          );
        })}
      </nav>

      {onSchemaChange && meta ? (
        <label className="flex items-center gap-2 text-[12px] text-[var(--color-text-3)]">
          domain pack
          <select
            value={schema}
            onChange={(event) => onSchemaChange(event.target.value)}
            className="rounded-[4px] border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-1 font-mono text-[12px] text-[var(--color-text)]"
          >
            {meta.schemas.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <div className="ml-auto">
        <CallCounter meta={meta} />
      </div>
    </header>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-[1280px]">{children}</div>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="px-4 py-8 text-[13px] text-[var(--color-text-3)]">{children}</p>
  );
}
