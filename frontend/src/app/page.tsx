import Link from "next/link";
import { apiGet, type Stats } from "@/lib/api";

async function getStats(): Promise<Stats | null> {
  try {
    return await apiGet<Stats>("/stats");
  } catch {
    return null;
  }
}

export default async function Home() {
  const stats = await getStats();
  const today = stats?.blocked_today ?? 0;
  const total = stats?.total_blocked ?? 0;

  return (
    <main className="mx-auto max-w-5xl px-6 pb-24 relative">
      <section className="py-24 text-center animate-fade-in">
        <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl lg:text-7xl">
          Block scams on every device<br/>
          <span className="bg-gradient-to-r from-brand to-red-400 bg-clip-text text-transparent drop-shadow-[0_0_20px_rgba(239,68,68,0.3)]">
            no app needed
          </span>
        </h1>
        <p className="mx-auto mt-8 max-w-2xl text-lg text-zinc-400/90 leading-relaxed">
          ScamLens replaces your DNS. Known scam sites are sinkholed immediately. Unknown
          domains are analyzed by AI in real time.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link href="/setup/android" className="group relative rounded-full bg-brand px-8 py-4 font-semibold text-white shadow-[0_0_20px_rgba(239,68,68,0.3)] transition-all hover:-translate-y-0.5 hover:shadow-[0_0_30px_rgba(239,68,68,0.5)] hover:bg-brand-dark">
            Set up in 2 minutes
          </Link>
          <Link href="/dashboard" className="rounded-full border border-white/10 bg-white/5 backdrop-blur-md px-8 py-4 font-semibold text-zinc-200 transition-all hover:bg-white/10 hover:text-white">
            See live dashboard
          </Link>
        </div>

        <div className="mt-16 animate-float inline-flex items-center gap-6 rounded-full border border-white/10 bg-white/5 backdrop-blur-xl px-8 py-4 text-sm text-zinc-300 shadow-2xl">
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
            </span>
            <span className="tabular-nums text-2xl font-bold text-white">
              {today.toLocaleString()}
            </span>
            <span className="text-zinc-400">blocked today</span>
          </div>
          <div className="h-6 w-px bg-white/10"></div>
          <div className="flex items-center gap-2 text-zinc-400">
            <span className="tabular-nums font-semibold text-white">{total.toLocaleString()}</span> all-time
          </div>
        </div>
      </section>

      <section className="grid gap-6 sm:grid-cols-3 relative z-10">
        <Step n={1} title="Change DNS" body="One setting on your device, router, or profile." />
        <Step n={2} title="We resolve for you" body="Queries hit our server. Known scams are blocked instantly." />
        <Step n={3} title="AI scans the rest" body="Unseen domains get a headless-browser + Claude verdict in seconds." />
      </section>

      <section className="mt-32 relative z-10">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-3xl font-bold tracking-tight">Set up on your device</h2>
          <div className="h-px flex-1 ml-8 bg-gradient-to-r from-white/10 to-transparent"></div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <PlatformCard href="/setup/android" label="Android" hint="Private DNS, Android 9+" />
          <PlatformCard href="/setup/ios" label="iPhone / iPad" hint="Configuration Profile" />
          <PlatformCard href="/setup/windows" label="Windows" hint="Network settings" />
          <PlatformCard href="/setup/macos" label="macOS" hint="System settings" />
          <PlatformCard href="/setup/linux" label="Linux" hint="NetworkManager / resolv.conf" />
          <PlatformCard href="/setup/router" label="Router" hint="Protect every network device" />
        </div>
      </section>
    </main>
  );
}

function Step({ n, title, body }: { n: number; title: string; body: string }) {
  return (
    <div className="group relative rounded-3xl border border-white/5 bg-gradient-to-b from-white/5 to-transparent p-8 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl hover:shadow-brand/10 hover:border-white/10">
      <div className="absolute top-0 right-0 p-6 opacity-10 transition-opacity group-hover:opacity-20 text-6xl font-black">
        {n}
      </div>
      <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand/10 text-sm font-bold text-brand shadow-[0_0_15px_rgba(239,68,68,0.2)]">
        {n}
      </div>
      <h3 className="mt-2 text-xl font-bold text-white">{title}</h3>
      <p className="mt-3 text-sm text-zinc-400 leading-relaxed">{body}</p>
    </div>
  );
}

function PlatformCard({ href, label, hint }: { href: string; label: string; hint: string }) {
  return (
    <Link
      href={href}
      className="group relative block overflow-hidden rounded-2xl border border-white/5 bg-white/5 p-6 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:bg-white/10 hover:shadow-xl hover:border-brand/30"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-white transition-colors group-hover:text-brand">{label}</h3>
        <span className="text-zinc-600 transition-transform duration-300 group-hover:translate-x-1 group-hover:text-brand">→</span>
      </div>
      <p className="mt-2 text-sm text-zinc-400">{hint}</p>
    </Link>
  );
}
