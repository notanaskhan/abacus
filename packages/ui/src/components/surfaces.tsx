import { CircleAlert, Inbox, LoaderCircle } from "lucide-react";
import type { HTMLAttributes, JSX, ReactNode } from "react";
import { cn } from "../cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      className={cn("rounded-[var(--radius-panel)] border border-line bg-surface p-4", className)}
      {...props}
    />
  );
}

export type Tone = "neutral" | "success" | "warning" | "danger" | "info";
const TONES: Record<Tone, string> = {
  neutral: "bg-sunken text-ink",
  success: "bg-ok-soft text-ok",
  warning: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
  info: "bg-info-soft text-info",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }): JSX.Element {
  return (
    <span
      className={cn(
        "inline-flex rounded px-2 py-0.5 text-xs font-semibold",
        TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded bg-sunken", className)}
      {...props}
    />
  );
}

export function Spinner({ label }: { label: string }): JSX.Element {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-muted">
      <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
      {label}
    </span>
  );
}

export function Alert({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}): JSX.Element {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-[var(--radius-panel)] border border-danger/30 bg-danger-soft p-4"
    >
      <CircleAlert aria-hidden="true" className="mt-0.5 size-4 text-danger" />
      <div className="flex-1 text-sm">
        <p className="font-semibold text-danger">{title}</p>
        {children !== undefined && <div className="text-ink">{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}): JSX.Element {
  return (
    <div className="flex flex-col items-center gap-2 rounded-[var(--radius-panel)] border border-dashed border-line bg-surface p-8 text-center">
      <Inbox aria-hidden="true" className="size-6 text-muted" />
      <p className="font-medium">{title}</p>
      {children !== undefined && <div className="text-sm text-muted">{children}</div>}
      {action}
    </div>
  );
}
