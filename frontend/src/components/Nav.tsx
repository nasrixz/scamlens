import Link from "next/link";

export function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-slate-950/60 backdrop-blur-md transition-all duration-300">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="group flex items-center gap-2 text-lg font-semibold transition-transform hover:scale-105">
          <span className="text-brand drop-shadow-[0_0_8px_rgba(239,68,68,0.8)] group-hover:animate-pulse">◉</span>
          <span className="tracking-tight text-white">ScamLens</span>
        </Link>
        <nav className="hidden sm:flex items-center gap-6 text-sm font-medium text-zinc-400">
          <Link href="/dashboard" className="hover:text-white transition-colors hover:text-glow">Dashboard</Link>
          <Link href="/setup/android" className="hover:text-white transition-colors hover:text-glow">Setup</Link>
          <Link href="/report" className="hover:text-white transition-colors hover:text-glow">Report</Link>
          <Link href="/about" className="hover:text-white transition-colors hover:text-glow">About</Link>
          <Link href="/login" className="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-200 hover:border-brand hover:text-brand transition-colors">Sign in</Link>
        </nav>
      </div>
    </header>
  );
}
