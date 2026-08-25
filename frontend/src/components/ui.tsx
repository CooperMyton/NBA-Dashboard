import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  right,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
      <div>
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1 className="font-display text-4xl font-semibold leading-none tracking-tight">{title}</h1>
        {subtitle && <p className="mt-2 text-fg-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <h2 className="eyebrow">{children}</h2>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="animate-rise rounded-lg border border-border bg-surface p-5">
      {title && <SectionTitle>{title}</SectionTitle>}
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="animate-rise rounded-lg border border-border bg-surface p-5">
      <div className="eyebrow">{label}</div>
      <div
        className="mt-2 font-display text-4xl font-semibold tabular"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-fg-muted">{hint}</div>}
    </div>
  );
}

export function TeamMark({ color, abbr }: { color: string; abbr: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        aria-hidden="true"
        className="inline-block h-4 w-1 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="font-semibold">{abbr}</span>
    </span>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <p className="py-12 text-center text-sm text-fg-muted">{message}</p>;
}
