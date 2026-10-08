import { Link, type LinkProps } from "@tanstack/react-router";
import type { JSX } from "react";

export interface TabItem {
  label: string;
  to: NonNullable<LinkProps["to"]>;
  params: NonNullable<LinkProps["params"]>;
  exact?: boolean;
}

/** Page tabs as links; TanStack marks the current one (`aria-current`, data-status). */
export function Tabs({ items, label }: { items: TabItem[]; label: string }): JSX.Element {
  return (
    <nav aria-label={label} className="flex flex-wrap gap-1 border-b border-line">
      {items.map((item) => (
        <Link
          key={item.label}
          to={item.to}
          params={item.params}
          activeOptions={{ exact: item.exact ?? false }}
          className="border-b-2 border-transparent px-3 py-2.5 text-sm text-muted hover:text-ink data-[status=active]:border-accent data-[status=active]:font-semibold data-[status=active]:text-ink"
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
