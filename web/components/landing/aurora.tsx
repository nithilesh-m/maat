/** Decorative animated background: drifting colour blobs over a faint grid. */
export function Aurora({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden className={`pointer-events-none absolute inset-0 -z-10 overflow-hidden ${className}`}>
      <div className="absolute -left-[10%] -top-[25%] size-[46rem] animate-aurora rounded-full bg-brand/30 blur-[110px]" />
      <div className="absolute -right-[8%] top-[5%] size-[40rem] animate-aurora-slow rounded-full bg-brand-2/30 blur-[120px]" />
      <div className="absolute bottom-[-30%] left-[25%] size-[36rem] animate-aurora rounded-full bg-brand/15 blur-[120px]" />
      <div className="bg-grid absolute inset-0" />
    </div>
  );
}
