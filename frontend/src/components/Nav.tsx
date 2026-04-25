"use client";

import { useState } from "react";
import Link from "next/link";
import { UserMenu } from "./UserMenu";

export function Nav() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-slate-950/60 backdrop-blur-md transition-all duration-300">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="group flex items-center gap-2 text-lg font-semibold transition-transform hover:scale-105">
          <span className="text-brand drop-shadow-[0_0_8px_rgba(239,68,68,0.8)] group-hover:animate-pulse">◉</span>
          <span className="tracking-tight text-white">ScamLens</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden sm:flex items-center gap-6 text-sm font-medium text-zinc-400">
          <Link href="/dashboard" className="hover:text-white transition-colors hover:text-glow">Dashboard</Link>
          <Link href="/setup/android" className="hover:text-white transition-colors hover:text-glow">Setup</Link>
          <Link href="/report" className="hover:text-white transition-colors hover:text-glow">Report</Link>
          <Link href="/about" className="hover:text-white transition-colors hover:text-glow">About</Link>
          <UserMenu />
        </nav>

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="sm:hidden flex flex-col gap-1.5 p-2"
          aria-label="Toggle menu"
        >
          <span className={`block h-0.5 w-6 bg-white transition-transform ${mobileOpen ? "rotate-45 translate-y-2" : ""}`} />
          <span className={`block h-0.5 w-6 bg-white transition-opacity ${mobileOpen ? "opacity-0" : ""}`} />
          <span className={`block h-0.5 w-6 bg-white transition-transform ${mobileOpen ? "-rotate-45 -translate-y-2" : ""}`} />
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <>
          <div className="fixed inset-0 z-40 bg-black/50 sm:hidden" onClick={() => setMobileOpen(false)} />
          <div className="absolute left-0 right-0 top-full z-50 border-b border-white/5 bg-slate-950/95 backdrop-blur-md px-6 py-4 sm:hidden">
            <nav className="flex flex-col gap-4 text-sm font-medium text-zinc-400">
              <Link href="/dashboard" onClick={() => setMobileOpen(false)} className="hover:text-white transition-colors">Dashboard</Link>
              <Link href="/setup/android" onClick={() => setMobileOpen(false)} className="hover:text-white transition-colors">Setup</Link>
              <Link href="/report" onClick={() => setMobileOpen(false)} className="hover:text-white transition-colors">Report</Link>
              <Link href="/about" onClick={() => setMobileOpen(false)} className="hover:text-white transition-colors">About</Link>
              <div className="pt-2 border-t border-white/5">
                <UserMenu />
              </div>
            </nav>
          </div>
        </>
      )}
    </header>
  );
}
