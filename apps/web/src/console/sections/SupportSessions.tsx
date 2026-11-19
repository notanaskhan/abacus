// Support sessions (G-04-T17; DEC-32, DEC-5701): every firm's support sessions, newest first, on the
// T1 list grammar: status tiles, then one row per session with the scope label, status, requester,
// the firm-side approver and its role, start and minutes. Metadata only: a row never opens firm
// content (the console sees tenant metadata, G-04 §3).
import type { PlatformSessionsOut } from "@abacus/api-client";
import { EmptyState, Pill, type PillVariant, StatusTile } from "@abacus/ui";
import type { JSX } from "react";
import { SECTIONS_COPY } from "./copy";

const C = SECTIONS_COPY.sessions;
const PILL: Record<string, PillVariant> = {
  requested: "amber",
  active: "green-tint",
  declined: "muted",
  revoked: "muted",
  ended: "neutral",
  expired: "muted",
};

function when(at: string | null): string {
  if (at === null) return "—";
  return new Date(at).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/Chicago",
  });
}

export function SupportSessions({ data }: { data: PlatformSessionsOut }): JSX.Element {
  return (
    <section
      aria-labelledby="console-sessions"
      data-console-section="sessions"
      className="flex flex-col gap-[12px]"
    >
      <h2 id="console-sessions" className="text-pane font-medium text-ink">
        {C.title}
      </h2>
      <div className="flex gap-[8px]">
        {(["requested", "active", "ended"] as const).map((k) => (
          <StatusTile key={k} count={data.counts[k] ?? 0} label={C.tiles[k]} />
        ))}
      </div>
      {data.items.length === 0 ? (
        <EmptyState title={C.empty} />
      ) : (
        <table className="w-full bg-card text-[13px]">
          <thead>
            <tr className="text-left text-ink-3">
              {C.columns.map((c) => (
                <th key={c} className="px-[10px] py-[6px] font-normal">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.items.map((s) => (
              <tr
                key={s.history.session_id}
                className="hairline-t"
                data-session={s.history.status}
              >
                <td className="px-[10px] py-[8px] text-ink">
                  {s.firm_display_name}
                  <span className="ml-[6px] text-ink-3">{s.tenant_code}</span>
                </td>
                <td className="px-[10px] py-[8px]">{C.scope[s.history.scope_kind]}</td>
                <td className="px-[10px] py-[8px]">
                  <Pill variant={PILL[s.history.status] ?? "neutral"} size="sm">
                    {C.status[s.history.status]}
                  </Pill>
                </td>
                <td className="px-[10px] py-[8px]">{s.history.requested_by}</td>
                <td className="px-[10px] py-[8px]">{s.history.approver_display_name ?? "—"}</td>
                <td className="px-[10px] py-[8px] tabular-nums">{when(s.history.started_at)}</td>
                <td className="px-[10px] py-[8px] tabular-nums">{s.history.duration_minutes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
