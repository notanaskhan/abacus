// Publications queue (G-04-T17; DEC-76 two-person publish; DEC-32, DEC-5701): help articles and
// platform reference sets waiting for a second platform admin. The server says who may publish
// (`can_publish`); the drafter's own draft shows Publish disabled with the reason beside it, never
// hidden (DF-04). Withdraw stays with a published version.
import type { ConsolePublicationOut, ConsolePublicationsOut } from "@abacus/api-client";
import { Button, EmptyState, Pill } from "@abacus/ui";
import type { JSX } from "react";
import { SECTIONS_COPY } from "./copy";

const C = SECTIONS_COPY.publications;

export interface PublicationsProps {
  data: ConsolePublicationsOut;
  onPublish?: ((p: ConsolePublicationOut) => void) | undefined;
  onWithdraw?: ((p: ConsolePublicationOut) => void) | undefined;
}

function Action({
  p,
  onPublish,
  onWithdraw,
}: { p: ConsolePublicationOut } & Omit<PublicationsProps, "data">): JSX.Element | null {
  if (p.status === "published")
    return (
      <Button variant="secondary" size="sm" onClick={() => onWithdraw?.(p)}>
        {C.withdraw}
      </Button>
    );
  if (p.status !== "draft") return null;
  const reason = `publish-reason-${p.id}`;
  return (
    <span className="flex items-center gap-[8px]">
      <Button
        size="sm"
        disabled={!p.can_publish}
        aria-describedby={p.can_publish ? undefined : reason}
        onClick={() => onPublish?.(p)}
      >
        {C.publish}
      </Button>
      {p.can_publish ? null : (
        <span id={reason} className="text-[12px] text-ink-3" data-publish-reason>
          {C.ownDraft}
        </span>
      )}
    </span>
  );
}

export function Publications({ data, onPublish, onWithdraw }: PublicationsProps): JSX.Element {
  return (
    <section
      aria-labelledby="console-publications"
      data-console-section="publications"
      className="flex flex-col gap-[12px]"
    >
      <h2 id="console-publications" className="text-pane font-medium text-ink">
        {C.title}
      </h2>
      {data.items.length === 0 ? (
        <EmptyState title={C.empty} />
      ) : (
        <table className="w-full bg-card text-[13px]">
          <thead>
            <tr className="text-left text-ink-3">
              {C.columns.map((c, i) => (
                <th key={`${c}-${String(i)}`} className="px-[10px] py-[6px] font-normal">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.items.map((p) => (
              <tr key={p.id} className="hairline-t" data-publication={p.status}>
                <td className="px-[10px] py-[8px]">{C.kind[p.kind]}</td>
                <td className="px-[10px] py-[8px] text-ink">{p.key}</td>
                <td className="px-[10px] py-[8px] tabular-nums">v{p.version}</td>
                <td className="px-[10px] py-[8px] tabular-nums">
                  {C.changes(p.rows_added, p.rows_changed, p.rows_removed)}
                </td>
                <td className="px-[10px] py-[8px]">{p.drafted_by}</td>
                <td className="px-[10px] py-[8px]">
                  <Pill variant={p.status === "published" ? "green-tint" : "neutral"} size="sm">
                    {C.status[p.status]}
                  </Pill>
                </td>
                <td className="px-[10px] py-[8px]">
                  <Action p={p} onPublish={onPublish} onWithdraw={onWithdraw} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
