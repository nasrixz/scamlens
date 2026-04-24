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
    <main className="mx-auto max-w-5xl px-6 pb-24">
      <section className="py-24 text-center">
        <h1 className="text-5xl font-bold tracking-tight sm:text-6xl">
          Block scams on every device —{" "}
          <span className="text-brand">no app needed</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-400">
          ScamLens replaces your DNS. Known scam sites are sinkholed. Unknown
          domains are analyzed by AI in real time.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link href="/setup/android" className="rounded-xl bg-brand px-6 py-3 font-semibold hover:bg-brand-dark">
            Set up in 2 minutes
          </Link>
          <Link href="/dashboard" className="rounded-xl border border-zinc-700 px-6 py-3 font-semibold text-zinc-200 hover:border-zinc-500">
            See live dashboard
          </Link>
        </div>

        <div className="mt-12 inline-flex items-center gap-6 rounded-full border border-zinc-800 bg-zinc-900/40 px-6 py-3 text-sm text-zinc-300">
          <span className="tabular-nums text-2xl font-bold text-brand">
            {today.toLocaleString()}
          </span>
          <span>scams blocked today</span>
          <span className="text-zinc-600">·</span>
          <span className="tabular-nums">{total.toLocaleString()} all-time</span>
        </div>
      </section>

      <section className="grid gap-6 sm:grid-cols-3">
        <Step n={1} title="Change DNS" body="One setting on your device, router, or profile." />
        <Step n={2} title="We resolve for you" body="Queries hit our server. Known scams are blocked instantly." />
        <Step n={3} title="AI scans the rest" body="Unseen domains get a headless-browser + Claude verdict in seconds." />
      </section>

      <section className="mt-20">
        <h2 className="text-2xl font-bold">Set up on your device</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <PlatformCard href="/setup/android" label="Android" hint="Private DNS, Android 9+" />
          <PlatformCard href="/setup/ios" label="iPhone / iPad" hint="Configuration Profile" />
          <PlatformCard href="/setup/windows" label="Windows" hint="Network settings" />
          <PlatformCard href="/setup/macos" label="macOS" hint="System settings" />
          <PlatformCard href="/setup/linux" label="Linux" hint="NetworkManager / resolv.conf" />
          <PlatformCard href="/setup/router" label="Router" hint="Protect every device on the network" />
        </div>
      </section>
    </main>
  );
}

function Step({ n, title, body }: { n: number; title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/30 p-6">
      <div className="text-xs font-bold uppercase tracking-wider text-brand">Step {n}</div>
      <div className="mt-2 text-lg font-semibold">{title}</div>
      <p className="mt-2 text-sm text-zinc-400">{body}</p>
    </div>
  );
}

function PlatformCard({ href, label, hint }: { href: string; label: string; hint: string }) {
  return (
    <Link
      href={href}
      className="block rounded-2xl border border-zinc-800 bg-zinc-900/30 p-5 transition hover:border-brand/60"
    >
      <div className="text-lg font-semibold">{label}</div>
      <div className="mt-1 text-sm text-zinc-400">{hint}</div>
    </Link>
  );
}
