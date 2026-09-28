import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, Inter } from "next/font/google";
import { DisclaimerBanner } from "@/components/disclaimer-banner";
import { TopNav } from "@/components/top-nav";
import "./globals.css";

// Heavy, characterful display for headlines; Inter for dense UI text; Plex Mono for all data.
const display = Bricolage_Grotesque({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
});

const sans = Inter({
  variable: "--font-sans-ui",
  subsets: ["latin"],
});

const mono = IBM_Plex_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Parallax — low-latency prediction-market intelligence",
  description:
    "A low-latency pipeline that watches Manifold's live bet stream, models calibrated probabilities, and detects logical-constraint and cross-source mispricings. Read-only; never trades.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`dark ${display.variable} ${sans.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="grain flex min-h-full flex-col">
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
