import type { Metadata } from "next";
import { JetBrains_Mono, Plus_Jakarta_Sans, Space_Grotesk } from "next/font/google";
import { AutoRefresh } from "@/components/auto-refresh";
import { CommandPalette } from "@/components/command-palette";
import { DisclaimerBanner } from "@/components/disclaimer-banner";
import { TopNav } from "@/components/top-nav";
import "./globals.css";

// Wide geometric grotesk for display; Plus Jakarta for UI; JetBrains Mono for all data.
const display = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const sans = Plus_Jakarta_Sans({
  variable: "--font-sans-ui",
  subsets: ["latin"],
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: {
    default: "Parallax — low-latency prediction-market intelligence",
    template: "%s · Parallax",
  },
  description:
    "A low-latency pipeline that watches Manifold's live bet stream, models calibrated probabilities, and detects logical-constraint and cross-source mispricings. Read-only; never trades.",
  metadataBase: new URL("http://localhost:3000"),
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`dark ${display.variable} ${sans.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="grain flex min-h-full flex-col">
        <div className="aurora" aria-hidden />
        <CommandPalette />
        <AutoRefresh />
        <DisclaimerBanner />
        <TopNav />
        <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-10 sm:px-8">{children}</main>
        <footer className="mx-auto w-full max-w-7xl px-5 py-10 text-sm text-muted-foreground sm:px-8">
          <div className="border-t border-border pt-6">
            Parallax — a portfolio project in low-latency systems and prediction-market modeling.
            Read-only; never trades.
          </div>
        </footer>
      </body>
    </html>
  );
}
