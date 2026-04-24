export function Footer() {
  return (
    <footer className="mt-24 relative border-t border-white/5 py-10 bg-slate-950/20 backdrop-blur-sm">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent"></div>
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 text-sm text-zinc-500">
        <span className="font-medium">© {new Date().getFullYear()} ScamLens</span>
        <span className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-brand"></span>
          </span>
          AI-powered DNS protection
        </span>
      </div>
    </footer>
  );
}
