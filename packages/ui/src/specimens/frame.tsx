import type { JSX, ReactNode } from "react";

// The frame the T0 specimens share: a sheet (pane with a 31px band header) of labelled rows, as
// the kit handoffs draw their reference boards.

export function Sheet({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: string | undefined;
  children: ReactNode;
}): JSX.Element {
  return (
    <section className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2">
      <div className="flex h-[31px] items-center gap-2 border-b-[0.5px] border-hair bg-band-hd px-3">
        <h2 className="flex-1 truncate text-section">{title}</h2>
        {meta !== undefined && <span className="text-meta text-ink-3">{meta}</span>}
      </div>
      <div className="flex flex-col">{children}</div>
    </section>
  );
}

export function Row({
  name,
  meaning,
  spec,
  children,
}: {
  name: string;
  meaning?: string | undefined;
  spec?: string | undefined;
  children: ReactNode;
}): JSX.Element {
  return (
    <div className="flex min-h-11 flex-wrap items-center gap-x-3.5 gap-y-2 border-b-[0.5px] border-hair px-3.5 py-2 last:border-b-0">
      <div className="w-[200px] shrink-0">
        <div className="text-dense font-medium">{name}</div>
        {meaning !== undefined && <div className="text-meta text-ink-3">{meaning}</div>}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">{children}</div>
      {spec !== undefined && <div className="ml-auto text-right text-meta text-ink-3">{spec}</div>}
    </div>
  );
}
