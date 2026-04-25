"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { userApi, AuthError } from "@/lib/userApi";

export function UserMenu() {
  const [user, setUser] = useState<{ email: string; role: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    userApi
      .me()
      .then((u) => {
        setUser(u);
        if (u && "Notification" in window && Notification.permission === "default") {
          Notification.requestPermission();
        }
      })
      .catch((e) => {
        if (!(e instanceof AuthError)) console.error(e);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = async () => {
    await userApi.logout();
    window.location.href = "/";
  };

  if (loading) return <div className="h-7 w-16 animate-pulse rounded-full bg-zinc-800" />;

  if (!user)
    return (
      <Link
        href="/login"
        className="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-200 hover:border-brand hover:text-brand transition-colors"
      >
        Sign in
      </Link>
    );

  return (
    <div className="relative">
      <button
        onClick={() => setMenuOpen(!menuOpen)}
        className="flex items-center gap-2 rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-200 hover:border-brand hover:text-brand transition-colors"
      >
        <span className="h-5 w-5 rounded-full bg-brand/20 flex items-center justify-center text-brand">
          {user.email[0].toUpperCase()}
        </span>
        <span className="hidden sm:inline">{user.email}</span>
      </button>

          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 z-20 mt-2 w-48 rounded-xl border border-zinc-700 bg-zinc-900 py-1 shadow-xl">
                <Link
                  href="/dashboard"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
                >
                  Dashboard
                </Link>
                {user.role === "admin" && (
                  <Link
                    href="/admin"
                    onClick={() => setMenuOpen(false)}
                    className="block px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
                  >
                    Admin
                  </Link>
                )}
                <Link
                  href="/account"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
                >
                  Account
                </Link>
                <button
                  onClick={handleLogout}
                  className="block w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-zinc-800"
                >
                  Sign out
                </button>
              </div>
            </>
          )}
    </div>
  );
}
