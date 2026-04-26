"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AuthError,
  type DependentsResponse,
  type Link as DepLink,
  type BlockEvent as ApiBlockEvent,
  type User,
  userApi,
} from "@/lib/userApi";
import { useLiveBlocks, type LiveBlock } from "@/lib/useLiveBlocks";
import { initPush, subscribePush, unsubscribePush } from "@/lib/push";

type Tab = "dependents" | "blocks" | "settings";

export default function AccountPage() {
  const router = useRouter();
  const [me, setMe] = useState<User | null>(null);
  const [deps, setDeps] = useState<DependentsResponse | null>(null);
  const [blocks, setBlocks] = useState<ApiBlockEvent[]>([]);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("dependents");
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);

  const { blocks: liveBlocks, connected } = useLiveBlocks(!!me);

  async function load() {
    try {
      const u = await userApi.me();
      setMe(u);
      const d = await userApi.dependents();
      setDeps(d);
      const b = await userApi.myBlocks(50);
      setBlocks(b.items);
    } catch (e) {
      if (e instanceof AuthError) router.replace("/login");
    }
  }

  useEffect(() => {
    load();
    initPush().then(setPushEnabled);
  }, []);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    try {
      const r = await userApi.invite(code.trim().toUpperCase());
      setMsg(`Invite sent to ${r.ward_email}. They must accept.`);
      setCode("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "invite failed");
    }
  }

  async function act(fn: () => Promise<unknown>) {
    setMsg(null);
    setErr(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "action failed");
    }
  }

  async function togglePush() {
    setPushLoading(true);
    try {
      if (pushEnabled) {
        await unsubscribePush();
        setPushEnabled(false);
      } else {
        const ok = await subscribePush();
        setPushEnabled(ok);
      }
    } finally {
      setPushLoading(false);
    }
  }

  if (!me || !deps) {
    return <div className="mx-auto max-w-2xl p-6 text-zinc-400">Loading…</div>;
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "dependents", label: "Dependents" },
    { key: "blocks", label: "Block Feed" },
    { key: "settings", label: "Settings" },
  ];

  return (
    <main className="mx-auto max-w-3xl px-6 py-10 space-y-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Your account</h1>
          <p className="text-sm text-zinc-400">{me.email}</p>
        </div>
        <button
          onClick={async () => {
            await userApi.logout().catch(() => undefined);
            router.replace("/");
          }}
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm hover:border-zinc-500"
        >
          Sign out
        </button>
      </header>

      {/* Invite code card */}
      <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
        <div className="text-xs uppercase tracking-wider text-zinc-500">
          Your invite code
        </div>
        <div className="mt-2 flex items-center gap-3">
          <code className="select-all rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 font-mono text-2xl tracking-widest">
            {me.invite_code}
          </code>
          <button
            onClick={() => navigator.clipboard.writeText(me.invite_code)}
            className="rounded-lg border border-zinc-700 px-3 py-2 text-xs hover:border-zinc-500"
          >
            Copy
          </button>
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          Share with someone who wants to add you as a dependent. They enter
          this code; you accept the invite below.
        </p>
      </section>

      {/* DoH token card */}
      {me.doh_token && (
        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
          <div className="text-xs uppercase tracking-wider text-zinc-500">
            Your personal DNS-over-HTTPS URL
          </div>
          <div className="mt-2">
            <code className="select-all break-all rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-mono block">
              https://{me.doh_token}.{me.dns_hostname ?? "dns.vendly.my"}/dns-query
            </code>
          </div>
          <p className="mt-2 text-xs text-zinc-500">
            Use this URL in your device&apos;s Private DNS / DoH settings.
            Blocked domains will be linked to your account so your guardians
            can see them.
          </p>
          <a
            href={`/api/setup/ios?token=${me.doh_token}`}
            download
            className="mt-3 inline-block rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-black hover:opacity-90"
          >
            Download macOS/iOS Profile
          </a>
        </section>
      )}

      {/* Tabs */}
      <nav className="flex gap-1 rounded-xl border border-zinc-800 bg-zinc-900/40 p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? "bg-brand text-white"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* ─── Dependents tab ─── */}
      {tab === "dependents" && (
        <>
          <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
            <div className="text-xs uppercase tracking-wider text-zinc-500">
              Add a dependent
            </div>
            <form onSubmit={invite} className="mt-3 flex flex-wrap gap-2">
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Their invite code (e.g. A4B9XK7Q)"
                className="flex-1 min-w-[240px] rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 font-mono text-sm tracking-wider outline-none focus:border-brand"
              />
              <button className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold hover:bg-brand-dark">
                Send invite
              </button>
            </form>
            {msg && <div className="mt-2 text-sm text-emerald-300">{msg}</div>}
            {err && <div className="mt-2 text-sm text-red-300">{err}</div>}
          </section>

          <Section title="Pending invites for you" empty="No invites waiting.">
            {deps.pending_incoming.map((l) => (
              <Row key={l.link_id} link={l}>
                <button
                  onClick={() => act(() => userApi.accept(l.link_id))}
                  className="rounded-lg bg-brand px-3 py-1 text-xs font-semibold text-white hover:bg-brand-dark"
                >
                  Accept
                </button>
                <button
                  onClick={() => act(() => userApi.reject(l.link_id))}
                  className="rounded-lg border border-zinc-700 px-3 py-1 text-xs hover:border-zinc-500"
                >
                  Reject
                </button>
              </Row>
            ))}
          </Section>

          <Section title="Your dependents (wards)" empty="None yet.">
            {deps.wards.map((l) => (
              <Row key={l.link_id} link={l}>
                <RemoveBtn onRemove={() => act(() => userApi.revoke(l.link_id))} />
              </Row>
            ))}
          </Section>

          <Section title="Watching over you (guardians)" empty="No guardians yet.">
            {deps.guardians.map((l) => (
              <Row key={l.link_id} link={l}>
                <RemoveBtn onRemove={() => act(() => userApi.revoke(l.link_id))} />
              </Row>
            ))}
          </Section>

          <Section title="Sent invites awaiting response" empty="None pending.">
            {deps.pending_outgoing.map((l) => (
              <Row key={l.link_id} link={l}>
                <RemoveBtn onRemove={() => act(() => userApi.revoke(l.link_id))} />
              </Row>
            ))}
          </Section>
        </>
      )}

      {/* ─── Block Feed tab ─── */}
      {tab === "blocks" && (
        <section className="space-y-4">
          {/* Live indicator */}
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                connected ? "bg-emerald-400 animate-pulse" : "bg-zinc-600"
              }`}
            />
            {connected ? "Live" : "Connecting…"}
            {liveBlocks.length > 0 && (
              <span className="text-zinc-400">
                · {liveBlocks.length} new
              </span>
            )}
          </div>

          {/* Live events first, then historical */}
          <div className="divide-y divide-zinc-800 rounded-xl border border-zinc-800 bg-zinc-900/40">
            {liveBlocks.length === 0 && blocks.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-zinc-500">
                No blocked attempts yet. When ScamLens blocks a scam domain
                for you or your dependents, it will appear here in real time.
              </div>
            )}
            {liveBlocks.map((b, i) => (
              <BlockRow key={`live-${i}`} block={b} live />
            ))}
            {blocks.map((b) => (
              <BlockRow key={b.id} block={b} />
            ))}
          </div>
        </section>
      )}

      {/* ─── Settings tab ─── */}
      {tab === "settings" && (
        <section className="space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">Push Notifications</div>
                <div className="text-xs text-zinc-500 mt-1">
                  Get notified when a scam is blocked for you or your
                  dependents.
                </div>
              </div>
              <button
                onClick={togglePush}
                disabled={pushLoading}
                className={`relative h-7 w-12 rounded-full transition-colors ${
                  pushEnabled ? "bg-brand" : "bg-zinc-700"
                } ${pushLoading ? "opacity-50" : ""}`}
              >
                <span
                  className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform ${
                    pushEnabled ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          </div>

          {/* iOS PWA notice */}
          <div className="rounded-2xl border border-amber-900/40 bg-amber-950/20 p-5">
            <div className="flex items-start gap-3">
              <span className="text-amber-400 text-lg">📱</span>
              <div>
                <div className="font-medium text-amber-200">
                  iOS / Safari users
                </div>
                <p className="text-xs text-amber-300/70 mt-1 leading-relaxed">
                  To receive push notifications on iPhone/iPad, add ScamLens
                  to your Home Screen first: tap the Share button (⬆) →
                  &quot;Add to Home Screen&quot;. Then open ScamLens from the
                  Home Screen icon and enable notifications here.
                </p>
              </div>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

/* ─── Shared sub-components ─── */

function Section({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: React.ReactNode;
}) {
  const arr = Array.isArray(children) ? children : [children];
  const isEmpty = arr.filter(Boolean).length === 0;
  return (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
        {title}
      </h2>
      <div className="mt-2 divide-y divide-zinc-800 rounded-xl border border-zinc-800 bg-zinc-900/40">
        {isEmpty ? (
          <div className="px-4 py-3 text-sm text-zinc-500">{empty}</div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

function Row({
  link,
  children,
}: {
  link: DepLink;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
      <div>
        <div className="font-medium text-zinc-100">{link.other_email}</div>
        <div className="text-xs text-zinc-500">
          code <span className="font-mono">{link.other_invite_code}</span> ·{" "}
          {link.role_in_link} · {link.status}
        </div>
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

function RemoveBtn({ onRemove }: { onRemove: () => void }) {
  return (
    <button
      onClick={() => {
        if (confirm("Remove this link?")) onRemove();
      }}
      className="rounded-lg border border-zinc-700 px-3 py-1 text-xs hover:border-red-500 hover:text-red-300"
    >
      Remove
    </button>
  );
}

function BlockRow({
  block,
  live,
}: {
  block: LiveBlock | BlockEvent | ApiBlockEvent;
  live?: boolean;
}) {
  const domain = block.domain || "?";
  const verdict = block.verdict || "blocked";
  const brand = block.mimics_brand;
  const ts = "created_at" in block ? block.created_at : null;

  return (
    <div
      className={`flex items-center justify-between gap-3 px-4 py-3 text-sm ${
        live ? "bg-brand/5 border-l-2 border-l-brand" : ""
      }`}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {live && (
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-brand animate-pulse" />
          )}
          <span className="font-mono text-zinc-100 truncate">{domain}</span>
        </div>
        <div className="text-xs text-zinc-500 mt-0.5">
          {verdict}
          {brand && ` · impersonates ${brand}`}
          {block.risk_score != null && ` · risk ${block.risk_score}%`}
        </div>
      </div>
      <div className="text-xs text-zinc-600 whitespace-nowrap">
        {ts
          ? new Date(ts).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })
          : "just now"}
      </div>
    </div>
  );
}

type BlockEvent = {
  id: number;
  domain: string;
  reason: string;
  verdict: string | null;
  risk_score: number | null;
  ai_confidence: number | null;
  mimics_brand: string | null;
  resolved_ip: string | null;
  user_id: number | null;
  created_at: string;
};
