import { CircleAlert, Inbox, LoaderCircle } from "lucide-react";
import type { HTMLAttributes, JSX, ReactNode } from "react";
import { cn } from "../cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      className={cn("rounded-lg border border-neutral-200 bg-white p-4", className)}
      {...props}
    />
  );
}

type Tone = "neutral" | "success" | "warning" | "danger";
const TONES: Record<Tone, string> = {
  neutral: "bg-neutral-100 text-neutral-800",
  success: "bg-green-100 text-green-900",
  warning: "bg-amber-100 text-amber-900",
  danger: "bg-red-100 text-red-900",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }): JSX.Element {
  return (
    <span
      className={cn("inline-flex rounded px-2 py-0.5 text-xs font-medium", TONES[tone], className)}
      {...props}
    />
  );
}

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded bg-neutral-200", className)}
      {...props}
    />
  );
}

export function Spinner({ label }: { label: string }): JSX.Element {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-neutral-600">
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
      className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4"
    >
      <CircleAlert aria-hidden="true" className="mt-0.5 size-4 text-red-700" />
      <div className="flex-1 text-sm">
        <p className="font-medium text-red-900">{title}</p>
        {children !== undefined && <div className="text-red-800">{children}</div>}
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
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-neutral-300 p-8 text-center">
      <Inbox aria-hidden="true" className="size-6 text-neutral-500" />
      <p className="font-medium">{title}</p>
      {children !== undefined && <div className="text-sm text-neutral-600">{children}</div>}
      {action}
    </div>
  );
}
