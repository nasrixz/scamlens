import Link from "next/link";

const PLATFORMS = [
  { slug: "android", label: "Android" },
  { slug: "ios", label: "iOS" },
  { slug: "windows", label: "Windows" },
  { slug: "macos", label: "macOS" },
  { slug: "linux", label: "Linux" },
  { slug: "router", label: "Router" },
];

export function SetupLayout({
  active,
  title,
  children,
}: {
  active: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-3xl font-bold">{title}</h1>
      <nav className="mt-6 flex flex-wrap gap-2">
        {PLATFORMS.map((p) => (
          <Link
            key={p.slug}
            href={`/setup/${p.slug}`}
            className={`rounded-full px-4 py-1.5 text-sm ${
              p.slug === active
                ? "bg-brand text-white"
                : "border border-zinc-700 text-zinc-300 hover:border-zinc-500"
            }`}
          >
            {p.label}
          </Link>
        ))}
      </nav>
      <div className="mt-8 space-y-6 text-zinc-200">{children}</div>
    </main>
  );
}
