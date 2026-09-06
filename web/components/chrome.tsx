"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Meta } from "@/lib/api";
import { ThemeToggle } from "@/components/theme";

/** Two entries, three screens: call detail is reached by clicking a ledger row.
 *  There is no fourth screen and no settings page. */
const SCREENS = [
  { href: "/", label: "Ledger" },
  { href: "/requeue", label: "Requeue" },
];

/** `Calls 13 / 20`, top right, on every screen. The budget is part of the
 *  design: it is the constraint the whole product is shaped around. */
export function CallCounter({ meta }: { meta: Meta | null }) {
  if (!meta) return null;
  const remaining = meta.calls_remaining;
  const color =
    remaining <= meta.live_call_floor
      ? "var(--contradicted-fg)"
      : remaining <= 5
        ? "var(--unresolved-fg)"
        : "var(--ink-2)";
  return (
    <span
      className="pill hidden items-center gap-1.5 px-3 py-1.5 sm:inline-flex"
      style={{ background: "var(--surface-solid)", boxShadow: "var(--shadow-float)" }}
      title={`${remaining} of ${meta.call_budget} free calls left; the last ${meta.live_call_floor} are reserved`}
    >
      <span className="text-[12px]" style={{ color: "var(--ink-3)" }}>
        Calls
      </span>
      <span className="font-mono text-[13px] font-medium tabular-nums" style={{ color }}>
        {meta.calls_used} / {meta.call_budget}
      </span>
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
    <header className="sticky top-0 z-20 px-4 pt-4 sm:px-6">
      <div className="panel flex items-center gap-3 px-3 py-2.5 sm:gap-4 sm:px-4">
        <Link
          href="/"
          className="font-mono text-[13px] font-medium tracking-[0.14em]"
          style={{ color: "var(--ink)" }}
        >
          ONRECORD
        </Link>

        <nav className="flex items-center gap-1">
          {SCREENS.map((screen) => {
            const active =
              screen.href === "/"
                ? pathname === "/"
                : pathname.startsWith(screen.href);
            return (
              <Link
                key={screen.href}
                href={screen.href}
                className="pill px-3 py-1.5 text-[13px]"
                style={{
                  background: active ? "var(--surface-solid)" : "transparent",
                  color: active ? "var(--ink)" : "var(--ink-3)",
                  boxShadow: active ? "var(--shadow-float)" : "none",
                }}
              >
                {screen.label}
              </Link>
            );
          })}
        </nav>

        {onSchemaChange && meta ? (
          <label
            className="pill ml-1 hidden items-center gap-2 px-3 py-1.5 md:inline-flex"
            style={{ background: "var(--surface-2)" }}
            title="Swapping this changes the domain with no code change"
          >
            <span className="text-[11px]" style={{ color: "var(--ink-3)" }}>
              pack
            </span>
            <select
              value={schema}
              onChange={(event) => onSchemaChange(event.target.value)}
              className="cursor-pointer border-none bg-transparent font-mono text-[12px] outline-none"
              style={{ color: "var(--ink)" }}
            >
              {meta.schemas.map((name) => (
                <option key={name} value={name} style={{ color: "#2a2437" }}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <div className="ml-auto flex items-center gap-2.5">
          <CallCounter meta={meta} />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-[1280px] pb-16">{children}</div>;
}

export function PageTitle({
  eyebrow,
  title,
  aside,
}: {
  eyebrow: string;
  title: string;
  aside?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 px-5 pb-5 pt-8 sm:px-7">
      <div>
        <p className="text-[13px]" style={{ color: "var(--ink-2)" }}>
          {eyebrow}
        </p>
        <h1
          className="mt-1 text-[34px] font-light leading-tight tracking-[-0.02em] sm:text-[40px]"
          style={{ color: "var(--ink)" }}
        >
          {title}
        </h1>
      </div>
      {aside}
    </div>
  );
}

export function Notice({
  children,
  tone = "quiet",
}: {
  children: React.ReactNode;
  tone?: "quiet" | "alert";
}) {
  return (
    <div className="px-4 sm:px-6">
      <p
        className="panel px-5 py-4 text-[13px] leading-relaxed"
        style={{
          color: tone === "alert" ? "var(--contradicted-fg)" : "var(--ink-2)",
        }}
      >
        {children}
      </p>
    </div>
  );
}

export function Label({ children }: { children: React.ReactNode }) {
  return (
    <h3
      className="text-[11px] font-medium uppercase tracking-[0.1em]"
      style={{ color: "var(--ink-3)" }}
    >
      {children}
    </h3>
  );
}
