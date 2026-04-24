import Link from "next/link";

export function Nav() {
  return (
    <header className="border-b border-zinc-800/80 bg-zinc-950/60 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold">
          <span className="text-brand">◉</span>
          <span>ScamLens</span>
        </Link>
        <nav className="flex items-center gap-6 text-sm text-zinc-300">
          <Link href="/dashboard" className="hover:text-white">Dashboard</Link>
          <Link href="/setup/android" className="hover:text-white">Setup</Link>
          <Link href="/report" className="hover:text-white">Report</Link>
          <Link href="/about" className="hover:text-white">About</Link>
        </nav>
      </div>
    </header>
  );
}
