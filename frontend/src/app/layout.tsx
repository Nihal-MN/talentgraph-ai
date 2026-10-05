import type { Metadata } from "next";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "TalentGraph AI — semantic talent search",
  description:
    "Semantic talent search and candidate rediscovery engine: lexical + vector retrieval, hybrid fusion, explainable ranking, measurable search quality.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
