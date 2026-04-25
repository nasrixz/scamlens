"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AuthError,
  type DependentsResponse,
  type Link as DepLink,
  type User,
  userApi,
} from "@/lib/userApi";

export default function AccountPage() {
  const router = useRouter();
  const [me, setMe] = useState<User | null>(null);
  const [deps, setDeps] = useState<DependentsResponse | null>(null);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const u = await userApi.me();
      setMe(u);
      const d = await userApi.dependents();
      setDeps(d);
    } catch (e) {
      if (e instanceof AuthError) router.replace("/login");
    }
  }

  useEffect(() => {
    load();
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

  if (!me || !deps) {
    return <div className="mx-auto max-w-2xl p-6 text-zinc-400">Loading…</div>;
  }

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
    </main>
  );
}

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
