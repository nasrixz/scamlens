"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { userApi } from "@/lib/userApi";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await userApi.register(email, password, name || undefined);
      router.push("/account");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-sm px-6 py-24">
      <h1 className="text-3xl font-bold">Create account</h1>
      <p className="mt-1 text-sm text-zinc-400">
        Already have one?{" "}
        <Link href="/login" className="text-brand hover:underline">
          Sign in
        </Link>
        .
      </p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        <label className="block">
          <span className="text-sm text-zinc-300">Display name (optional)</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 outline-none focus:border-brand"
          />
        </label>
        <label className="block">
          <span className="text-sm text-zinc-300">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            className="mt-1 w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 outline-none focus:border-brand"
          />
        </label>
        <label className="block">
          <span className="text-sm text-zinc-300">Password (min 10 chars)</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={10}
            autoComplete="new-password"
            className="mt-1 w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 outline-none focus:border-brand"
          />
        </label>
        <button
          disabled={busy}
          className="w-full rounded-xl bg-brand px-6 py-3 font-semibold hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? "Creating…" : "Create account"}
        </button>
        {err && <p className="text-sm text-red-400">{err}</p>}
      </form>
    </main>
  );
}
