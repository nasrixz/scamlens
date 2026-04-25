import "../globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "ScamLens — AI DNS that blocks scams",
  description: "Block scam websites on every device. No app needed.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} font-sans`}>
      <body className="min-h-screen bg-slate-950 text-zinc-100 antialiased relative selection:bg-brand/30">
        {/* Ambient Background Gradient */}
        <div className="pointer-events-none fixed inset-0 flex justify-center z-[-1]">
          <div className="absolute top-[-20%] w-[800px] h-[600px] bg-brand/10 rounded-full blur-[120px] opacity-60" />
        </div>
        
        <Nav />
        {children}
        <Footer />
      </body>
    </html>
  );
}
