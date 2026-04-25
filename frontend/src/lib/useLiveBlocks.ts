/**
 * SSE hook — live block-event stream for the current user.
 *
 * Connects to /api/events/blocks with credentials. Each message is a
 * block event JSON. Auto-reconnects with exponential backoff.
 */
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { API_BASE } from "./api";

export type LiveBlock = {
  user_id: number;
  domain: string;
  reason: string | null;
  verdict: string | null;
  risk_score: number | null;
  confidence: number | null;
  mimics_brand: string | null;
  resolved_ip: string | null;
};

export function useLiveBlocks(enabled: boolean) {
  const [blocks, setBlocks] = useState<LiveBlock[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const backoffRef = useRef(2000);

  const connect = useCallback(() => {
    if (!enabled) return;

    const url = `${API_BASE}/events/blocks`;
    const es = new EventSource(url, { withCredentials: true });
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      backoffRef.current = 2000;
    };
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as LiveBlock;
        setBlocks((prev) => [data, ...prev].slice(0, 200));
      } catch {
        // Ignore non-JSON keepalives.
      }
    };
    es.onerror = () => {
      setConnected(false);
      es.close();
      // Reconnect with backoff.
      const delay = backoffRef.current;
      backoffRef.current = Math.min(delay * 2, 60_000);
      setTimeout(connect, delay);
    };
  }, [enabled]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      setConnected(false);
    };
  }, [connect]);

  const clear = useCallback(() => setBlocks([]), []);
  return { blocks, connected, clear };
}
