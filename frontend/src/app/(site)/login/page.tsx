"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { userApi } from "@/lib/userApi";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await userApi.login(email, password);
      if ("Notification" in window && Notification.permission === "default") {
        await Notification.requestPermission();
      }
      router.push("/account");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-sm px-6 py-24">
      <h1 className="text-3xl font-bold">Sign in</h1>
      <p className="mt-1 text-sm text-zinc-400">
        Or{" "}
        <Link href="/register" className="text-brand hover:underline">
          create an account
        </Link>
        .
      </p>
      <form onSubmit={submit} className="mt-8 space-y-4">
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
          <span className="text-sm text-zinc-300">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className="mt-1 w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 outline-none focus:border-brand"
          />
        </label>
        <button
          disabled={busy}
          className="w-full rounded-xl bg-brand px-6 py-3 font-semibold hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {err && <p className="text-sm text-red-400">{err}</p>}
      </form>
    </main>
  );
}
