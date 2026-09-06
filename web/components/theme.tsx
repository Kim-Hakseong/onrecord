"use client";

import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "onrecord-theme";

/** Runs before paint so a dark-mode reader never gets a flash of the light
 *  gradient. Inlined as a string because it has to execute before React. */
export const themeScript = `(function(){try{
  var stored = localStorage.getItem("${STORAGE_KEY}");
  var system = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = stored === "light" || stored === "dark" ? stored : system;
}catch(e){document.documentElement.dataset.theme="light";}})();`;

function current(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(current());
  }, []);

  const toggle = () => {
    const next: Theme = current() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* private mode: the choice just does not persist */
    }
    setTheme(next);
  };

  return { theme, toggle };
}

/** The half-filled circle from the reference — light on one side, dark on the
 *  other, so the control shows both states rather than naming one. */
export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="pill grid h-9 w-9 place-items-center border"
      style={{
        background: "var(--surface-solid)",
        borderColor: "var(--hairline)",
        boxShadow: "var(--shadow-float)",
      }}
    >
      <svg width="17" height="17" viewBox="0 0 20 20" aria-hidden="true">
        <circle
          cx="10"
          cy="10"
          r="7.25"
          fill="none"
          stroke="var(--ink)"
          strokeWidth="1.4"
        />
        <path d="M10 2.75a7.25 7.25 0 0 0 0 14.5z" fill="var(--ink)" />
      </svg>
    </button>
  );
}
