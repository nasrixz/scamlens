export default function About() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold">About ScamLens</h1>

      <section className="mt-8 space-y-4 text-zinc-200">
        <h2 className="text-xl font-semibold">Mission</h2>
        <p>
          Phishing, fake-bank pages, and fraudulent investment schemes work
          because they look real at a glance. Blocklists catch the ones security
          teams have already reported — scammers just spin up new domains. ScamLens
          pairs a classic DNS sinkhole with a real-time AI verdict, so fresh scams
          get caught the first time anyone loads them.
        </p>

        <h2 className="text-xl font-semibold">How the AI works</h2>
        <p>
          When our DNS resolver sees a domain it has never scored, the query is
          still answered instantly — from upstream — so you don&apos;t wait. In the
          background, a headless browser loads the page, captures the HTML and a
          screenshot, and asks a vision-enabled model (Claude by default, Gemini
          optional) to flag scam patterns: fake login forms, urgency tactics,
          typosquatting, prize scams, and credential theft. The verdict is cached,
          so the second visitor gets blocked instantly.
        </p>

        <h2 className="text-xl font-semibold">What we log</h2>
        <ul className="list-disc space-y-1 pl-6">
          <li>Blocked domain, timestamp, and the reason the AI gave.</li>
          <li>The querying client IP, for abuse/rate-limit protection only.</li>
          <li>No full query logs. No cleartext browsing history. No payloads.</li>
        </ul>

        <h2 className="text-xl font-semibold">Safe by default</h2>
        <p>
          Unknown domains are <em>forwarded</em>, not blocked. The AI only sinkholes
          a domain after classifying it as scam with high confidence. You can report
          false positives on the <a href="/report" className="text-brand hover:underline">report page</a>.
        </p>
      </section>
    </main>
  );
}
