import Link from "next/link";

const PLATFORMS = [
  {
    slug: "android",
    label: "Android",
    hint: "Private DNS (9+). No app needed.",
    time: "~1 min",
  },
  {
    slug: "ios",
    label: "iPhone / iPad",
    hint: "One-click Configuration Profile.",
    time: "~2 min",
  },
  {
    slug: "windows",
    label: "Windows",
    hint: "Network settings → Manual DNS.",
    time: "~2 min",
  },
  {
    slug: "macos",
    label: "macOS",
    hint: "Install the iOS profile, or set DNS manually.",
    time: "~2 min",
  },
  {
    slug: "linux",
    label: "Linux",
    hint: "NetworkManager / systemd-resolved.",
    time: "~2 min",
  },
  {
    slug: "router",
    label: "Router",
    hint: "Protects every device on the network.",
    time: "~5 min",
  },
];

export default function SetupHub() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold">Set up ScamLens</h1>
      <p className="mt-2 text-zinc-400">Pick your platform. All methods are reversible.</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {PLATFORMS.map((p) => (
          <Link
            key={p.slug}
            href={`/setup/${p.slug}`}
            className="block rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 transition hover:border-brand/60"
          >
            <div className="flex items-center justify-between">
              <div className="text-lg font-semibold">{p.label}</div>
              <span className="text-xs text-zinc-500">{p.time}</span>
            </div>
            <div className="mt-2 text-sm text-zinc-400">{p.hint}</div>
          </Link>
        ))}
      </div>
    </main>
  );
}
