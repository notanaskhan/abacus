import { Link, type LinkProps } from "@tanstack/react-router";
import type { JSX } from "react";

export interface TabItem {
  label: string;
  to: NonNullable<LinkProps["to"]>;
  params: NonNullable<LinkProps["params"]>;
  exact?: boolean;
}

/** Page tabs as links on a segmented track (TASK-092): the current one is a white pill on a
 * ring; TanStack marks it (`aria-current`, data-status). */
export function Tabs({ items, label }: { items: TabItem[]; label: string }): JSX.Element {
  return (
    <nav
      aria-label={label}
      className="flex w-fit max-w-full flex-wrap gap-0.5 rounded-full bg-nav-fill p-1"
    >
      {items.map((item) => (
        <Link
          key={item.label}
          to={item.to}
          params={item.params}
          activeOptions={{ exact: item.exact ?? false }}
          className="flex h-[28px] items-center rounded-full px-3.5 text-[13.5px] tracking-[-0.005em] text-ink-2 transition-colors hover:text-ink data-[status=active]:bg-card data-[status=active]:font-medium data-[status=active]:text-ink data-[status=active]:shadow-e1"
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
