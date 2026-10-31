import type { Metadata } from "next";
import Link from "next/link";
import { Manrope, Pixelify_Sans } from "next/font/google";
import "./globals.css";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope" });
const pixelify = Pixelify_Sans({ subsets: ["latin"], variable: "--font-pixelify" });

export const metadata: Metadata = {
  title: "WAGE.md",
  description:
    "DOL-verified salaries by company, role, and level. Agent-discoverable, every number cited.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${manrope.variable} ${pixelify.variable} min-h-screen bg-neutral-100 font-sans text-neutral-900 antialiased`}>
        <header>
          <nav className="mx-auto flex max-w-4xl justify-center gap-7 px-6 py-6 text-sm text-neutral-700">
            <Link href="/negotiate" className="hover:text-neutral-900">Negotiate</Link>
            <Link href="/briefs" className="hover:text-neutral-900">Index</Link>
            <Link href="/about" className="hover:text-neutral-900">About</Link>
          </nav>
        </header>
        <main className="mx-auto max-w-4xl px-6 py-12">{children}</main>
        <footer className="mx-auto max-w-4xl px-6 py-10 text-xs text-neutral-400">
          Built with Tiger Data · OpenAI.
        </footer>
      </body>
    </html>
  );
}
