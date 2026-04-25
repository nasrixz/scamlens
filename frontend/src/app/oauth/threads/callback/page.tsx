import { headers } from "next/headers";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ code?: string; error?: string; error_description?: string }> };

export default async function ThreadsOAuthCallback({ searchParams }: Props) {
  const params = await searchParams;
  const code = params.code ?? null;
  const error = params.error ?? null;
  const description = params.error_description ?? null;

  // No-op — just renders the code so the operator can copy it on the VPS
  // step that exchanges code → token. We never store the code here.
  await headers();

  if (error) {
    return (
      <main className="mx-auto max-w-xl px-6 py-16 text-zinc-100">
        <h1 className="text-2xl font-bold text-red-400">Threads authorization failed</h1>
        <p className="mt-2 text-sm text-zinc-300">{description ?? error}</p>
      </main>
    );
  }

  if (!code) {
    return (
      <main className="mx-auto max-w-xl px-6 py-16 text-zinc-100">
        <h1 className="text-2xl font-bold">Threads OAuth callback</h1>
        <p className="mt-2 text-sm text-zinc-400">
          This page captures the OAuth authorization code returned by Threads.
          Visit it via the Threads authorize URL to receive a code.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-xl px-6 py-16 text-zinc-100">
      <h1 className="text-2xl font-bold">Authorized ✓</h1>
      <p className="mt-2 text-sm text-zinc-300">
        Copy this code and exchange it for an access token on your VPS.
      </p>
      <pre className="mt-6 select-all overflow-x-auto rounded-xl border border-zinc-700 bg-zinc-900 p-4 font-mono text-sm break-all">
        {code}
      </pre>
      <h2 className="mt-8 text-lg font-semibold">Next step (run on the VPS)</h2>
      <pre className="mt-3 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-xs leading-snug">{`APP_ID='<your_app_id>'
APP_SECRET='<your_app_secret>'
CODE='${code}'

curl -s -X POST "https://graph.threads.net/oauth/access_token" \\
  -F "client_id=$APP_ID" \\
  -F "client_secret=$APP_SECRET" \\
  -F "grant_type=authorization_code" \\
  -F "redirect_uri=https://scamlens.vendly.my/oauth/threads/callback" \\
  -F "code=$CODE"`}</pre>
      <p className="mt-4 text-xs text-zinc-500">
        Codes are short-lived (≈10 minutes) and single-use. Run the exchange now.
      </p>
    </main>
  );
}
