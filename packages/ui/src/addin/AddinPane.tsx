// AddinPane and AddinChrome C-39 (F-08-T17; TASK-8849; F-08 §E1; handoff T22 a–g; INV-1, INV-5;
// DEC-5846): the Office add-in pane, host-agnostic — no Office.js import (W-04 owns the host, the
// manifest and NAA/SSO under ADR P-20). 350 px: header 48 (monogram, "Accrued", context, the
// signed-in initials, "···" Settings · Help · Sign out), Segmented sm Link · Tickmarks · Sign-off ·
// Changes (amber count on Changes), a body of cards (KV rows 30, one primary 32 per card) and a
// footer 40 ("Synced <time>" or, offline, "Last synced <time>"; "Open in Accrued ↗"). Offline adds
// the 32 px amber bar and disables Sign-off; signed out is the SSO card with the firm's name from
// branding (never a constant). Every action is an intent: "Sign off again as <name>…" only opens
// the sign-off dialog (onOpenSignOff); the pane never signs.
import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { Pill } from "../components/pill";
import { Segmented } from "../components/tabs";
import { Icon } from "../icons";

export const ADDIN_W = 350;
export const ADDIN_TABS = ["Link", "Tickmarks", "Sign-off", "Changes"] as const;
export type AddinTab = (typeof ADDIN_TABS)[number];
export const TICKMARKS = [
  { glyph: "✓", label: "Agreed to source" },
  { glyph: "⊕", label: "Footed" },
  { glyph: "∧", label: "Cross-footed" },
  { glyph: "◊", label: "Traced to TB" },
  { glyph: "¢", label: "Recalculated" },
] as const;

export interface AddinChange {
  cell: string;
  by: string;
  from: string;
  to: string;
}

export interface AddinSignOff {
  /** The preparer slot: open, signed, stale (changed after sign-off) or locked. */
  state: "open" | "signed" | "stale" | "locked";
  signer?: string;
  initials?: string;
}

export interface AddinPaneProps {
  host: "excel" | "word";
  signedIn: boolean;
  /** The firm's name from branding data (DF-30). */
  firmName: string;
  context: string;
  initials?: string;
  tab: AddinTab;
  onTab?: (tab: AddinTab) => void;
  offline?: boolean;
  /** The queued intents while offline ("2 changes waiting to sync"). */
  queued?: number;
  syncedAt: string;
  /** The selected cell and its link, if any. */
  selection?: { cell: string; linked?: { file: string; page: number } } | undefined;
  signOff: AddinSignOff;
  changes: readonly AddinChange[];
  /** Word: values changed in Accrued since the document's last update. */
  incoming?: readonly AddinChange[];
  onSignIn?: () => void;
  onLink?: () => void;
  onTickmark?: (label: string) => void;
  onOpenSignOff?: () => void;
  onUpdateDocument?: () => void;
  onChangeHistory?: () => void;
  onOpenInAccrued?: () => void;
}

function Card({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <section
      aria-label={title}
      data-addin-card=""
      className="flex flex-col gap-[8px] rounded-[10px] bg-card p-[12px] shadow-e1"
    >
      <header>
        <h3 className="text-[13px] font-medium text-ink">{title}</h3>
        {meta ? <p className="text-[11.5px] text-ink-3">{meta}</p> : null}
      </header>
      {children}
    </section>
  );
}

function Kv({ k, v }: { k: string; v: ReactNode }): JSX.Element {
  return (
    <div className="flex h-[30px] items-center justify-between">
      <span className="text-[12px] text-ink-2">{k}</span>
      <span className="text-[12.5px] text-ink">{v}</span>
    </div>
  );
}

export function AddinChrome({
  context,
  initials,
  tab,
  onTab,
  changes,
  offline,
  syncedAt,
  onOpenInAccrued,
  children,
}: {
  context: string;
  initials?: string | undefined;
  tab?: AddinTab | undefined;
  onTab?: ((t: AddinTab) => void) | undefined;
  changes?: number;
  offline?: boolean | undefined;
  syncedAt: string;
  onOpenInAccrued?: (() => void) | undefined;
  children: ReactNode;
}): JSX.Element {
  return (
    <aside
      data-addin=""
      style={{ width: ADDIN_W }}
      className="flex h-full flex-col border-l border-hair bg-card"
    >
      <header className="flex h-[48px] flex-none items-center gap-[6px] border-b border-hair px-[12px]">
        <span aria-hidden className="h-[16px] w-[16px] rounded-[4px] bg-ink" />
        <span className="text-[13.5px] font-medium text-ink">Accrued</span>
        <span className="truncate text-[11.5px] text-ink-3">{context}</span>
        {initials ? (
          <span className="ml-auto flex h-[20px] w-[20px] items-center justify-center rounded-full bg-nested text-[10px] text-ink">
            {initials}
          </span>
        ) : (
          <span className="ml-auto" />
        )}
        <span className="text-[12px] text-ink-3" aria-label="More">
          ···
        </span>
      </header>
      {tab !== undefined ? (
        <div className="m-[10px] flex justify-center">
          <Segmented
            size="small"
            label="Add-in"
            options={ADDIN_TABS.map((t) =>
              t === "Changes" && changes ? `Changes ${String(changes)}` : t,
            )}
            active={tab === "Changes" && changes ? `Changes ${String(changes)}` : tab}
            {...(onTab
              ? {
                  onChange: (v: string) => {
                    onTab(ADDIN_TABS.find((t) => v.startsWith(t)) ?? "Link");
                  },
                }
              : {})}
          />
        </div>
      ) : null}
      {offline ? (
        <p
          role="status"
          data-offline=""
          className="flex h-[32px] flex-none items-center bg-amber-tint px-[12px] text-[12px] text-amber-ink"
        >
          Offline · changes sync when you reconnect
        </p>
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col gap-[10px] overflow-auto bg-shell p-[10px]">
        {children}
      </div>
      <footer className="flex h-[40px] flex-none items-center border-t border-hair px-[12px]">
        <span className="flex items-center gap-[6px] text-[11.5px] text-ink-3">
          <span
            aria-hidden
            className={cn("h-[6px] w-[6px] rounded-full", offline ? "bg-ink-4" : "bg-green-ink")}
          />
          {offline ? `Last synced ${syncedAt}` : `Synced ${syncedAt}`}
        </span>
        <button
          type="button"
          onClick={onOpenInAccrued}
          className="ml-auto inline-flex items-center gap-[4px] text-[12.5px] font-medium text-ink"
        >
          Open in Accrued{" "}
          <Icon name="square-arrow-out-up-right" size={12} className="text-ink-3" />
        </button>
      </footer>
    </aside>
  );
}

export function AddinPane(p: AddinPaneProps): JSX.Element {
  if (!p.signedIn) {
    return (
      <AddinChrome context={p.context} syncedAt={p.syncedAt} onOpenInAccrued={p.onOpenInAccrued}>
        <div className="flex flex-1 items-center justify-center">
          <Card title="Sign in to Accrued">
            <p className="text-[12.5px] text-ink-2">
              Use your firm&apos;s single sign-on. Links, tickmarks and sign-offs stay with the
              workpaper.
            </p>
            <Button
              variant="primary"
              onClick={p.onSignIn}
            >{`Sign in with ${p.firmName} SSO`}</Button>
          </Card>
        </div>
      </AddinChrome>
    );
  }
  const locked = p.signOff.state === "locked";
  return (
    <AddinChrome
      context={p.context}
      initials={p.initials}
      tab={p.tab}
      onTab={p.onTab}
      changes={p.changes.length}
      offline={p.offline}
      syncedAt={p.syncedAt}
      onOpenInAccrued={p.onOpenInAccrued}
    >
      {p.offline && p.queued ? (
        <p className="text-[12px] text-amber-ink">{`${String(p.queued)} changes waiting to sync`}</p>
      ) : null}
      {p.host === "word" && p.incoming && p.incoming.length > 0 ? (
        <Card title={`Incoming changes (${String(p.incoming.length)})`}>
          {p.incoming.map((c) => (
            <Kv key={c.cell} k={c.cell} v={`${c.from} → ${c.to}`} />
          ))}
          <Button variant="primary" onClick={p.onUpdateDocument}>
            Update document
          </Button>
          <Button variant="secondary" onClick={p.onChangeHistory}>
            Change history
          </Button>
        </Card>
      ) : null}
      {p.tab === "Link" ? (
        <Card title="Link" {...(p.selection ? { meta: p.selection.cell } : {})}>
          {p.selection?.linked ? (
            <Kv
              k="Linked to evidence"
              v={`${p.selection.linked.file} · p.${String(p.selection.linked.page)}`}
            />
          ) : (
            <p className="text-[12.5px] text-ink-2">Select a cell to link it to evidence.</p>
          )}
          <Button variant="primary" disabled={!p.selection || locked} onClick={p.onLink}>
            Link to evidence…
          </Button>
        </Card>
      ) : null}
      {p.tab === "Tickmarks" ? (
        <Card title="Tickmarks">
          {TICKMARKS.map((t) => (
            <Button
              key={t.label}
              variant="secondary"
              size="sm"
              disabled={locked}
              onClick={() => p.onTickmark?.(t.label)}
            >
              {`${t.glyph} ${t.label}`}
            </Button>
          ))}
        </Card>
      ) : null}
      {p.tab === "Sign-off" ? (
        <Card title="Sign-off" meta="Preparer">
          <Kv
            k="P"
            v={
              p.signOff.state === "stale" ? (
                <span
                  data-slot="stale"
                  className="text-amber-ink"
                >{`${p.signOff.initials ?? ""} !`}</span>
              ) : p.signOff.state === "signed" || locked ? (
                <span data-slot="signed">{p.signOff.initials ?? ""}</span>
              ) : (
                <span data-slot="open" className="text-ink-3">
                  —
                </span>
              )
            }
          />
          {locked ? (
            <Pill variant="green">Signed off · locked</Pill>
          ) : (
            <Button variant="primary" disabled={p.offline === true} onClick={p.onOpenSignOff}>
              {p.signOff.state === "stale" && p.signOff.signer
                ? `Sign off again as ${p.signOff.signer}…`
                : "Sign off…"}
            </Button>
          )}
        </Card>
      ) : null}
      {p.tab === "Changes" ? (
        <Card
          title="Changes"
          meta={
            p.changes.length ? `${String(p.changes.length)} changed after sign-off` : "No changes"
          }
        >
          {p.changes.map((c) => (
            <Kv key={c.cell} k={c.cell} v={`${c.from} → ${c.to} · ${c.by}`} />
          ))}
        </Card>
      ) : null}
    </AddinChrome>
  );
}
