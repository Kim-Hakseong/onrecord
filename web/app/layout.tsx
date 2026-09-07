import type { Metadata } from "next";
import { Field, Grain } from "@/components/field";
import { themeScript } from "@/components/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "ONRECORD",
  description: "Phone calls that end in records, not summaries.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        {/* Applies the stored theme before first paint. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        {/* Gradient (CSS) → dot field → content → grain. */}
        <Field />
        {children}
        <Grain />
      </body>
    </html>
  );
}
