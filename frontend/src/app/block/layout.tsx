import "../globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Blocked — ScamLens",
  description: "ScamLens has blocked this site.",
  robots: { index: false, follow: false },
};

// Standalone layout: no Nav / no Footer. Block page is hostile-domain UX
// — we don't want our marketing chrome (or nav links to "/dashboard") to
// stay on the scam host's URL bar.
export default function BlockLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} font-sans`}>
      <body className="min-h-screen bg-slate-950 text-zinc-100 antialiased relative selection:bg-brand/30">
        <div className="pointer-events-none fixed inset-0 flex justify-center z-[-1]">
          <div className="absolute top-[-20%] w-[800px] h-[600px] bg-brand/10 rounded-full blur-[120px] opacity-50" />
        </div>
        {children}
      </body>
    </html>
  );
}
