// The Paperclip context picker (F-07-T07; handoff T4 "Paperclip chip → context picker popover
// (Client record, Documents, Workpapers)"; O1 card, 380 wide). It lists only what the host (L3)
// passes in, grouped by kind, already permission-filtered on the server: the kit never asks for
// more, never searches on its own and never shows a record it was not given (walls and need-to-know
// are the server's; INV-3). A loading kind shows a spinner row; an attached item shows the olive
// check and detaches on a second press. Nothing here fetches.
import type { JSX, ReactNode } from "react";
import { Spinner } from "../../components/motion";
import { Icon } from "../../icons";
import { Popover } from "../../overlays/popover";
import { CONTEXT_KINDS, type ContextItem, type ContextKind } from "./empty-session";

export interface ContextPickerProps {
  trigger: ReactNode;
  /** The records L3 passes in, by kind; a kind absent here shows its empty line. */
  items: Readonly<Partial<Record<ContextKind, readonly ContextItem[]>>>;
  /** Ids of the records the session already holds. */
  attached: ReadonlySet<string>;
  /** Kinds still loading (a spinner row). */
  loading?: ReadonlySet<ContextKind>;
  /** Open on one kind only (a "+ Documents" chip); all three otherwise. */
  kind?: ContextKind | null;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  onAttach: (item: ContextItem) => void;
  onDetach: (item: ContextItem) => void;
  forceState?: "open";
}

export const CONTEXT_PICKER_WIDTH = 380;

const EMPTY: Record<ContextKind, string> = {
  client_record: "No client record on this session yet.",
  documents: "No documents to add.",
  workpapers: "No workpapers to add.",
};

export function ContextPicker({
  trigger,
  items,
  attached,
  loading = new Set(),
  kind = null,
  open,
  onOpenChange,
  onAttach,
  onDetach,
  forceState,
}: ContextPickerProps): JSX.Element {
  const kinds = CONTEXT_KINDS.filter((k) => kind === null || k.kind === kind);
  return (
    <Popover
      trigger={trigger}
      align="start"
      width={CONTEXT_PICKER_WIDTH}
      label="Add context"
      open={open}
      onOpenChange={onOpenChange}
      forceState={forceState}
    >
      <div data-kit="ContextPicker" className="flex flex-col gap-[10px]">
        {kinds.map(({ kind: k, label }) => {
          const rows = items[k] ?? [];
          const busy = loading.has(k);
          return (
            <section key={k} data-context-kind={k} aria-label={label} className="flex flex-col">
              <h3 className="mb-[2px] text-[11.5px] font-medium text-ink-3">{label}</h3>
              {busy ? (
                <div data-loading className="flex h-[34px] items-center gap-[8px] text-ink-3">
                  <Spinner size={12} label="Loading" showLabel={false} />
                  <span className="text-[12.5px]">Loading…</span>
                </div>
              ) : rows.length === 0 ? (
                <p className="py-[8px] text-[12.5px] text-ink-3">{EMPTY[k]}</p>
              ) : (
                <ul className="flex flex-col">
                  {rows.map((item) => {
                    const on = attached.has(item.id);
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          role="menuitemcheckbox"
                          aria-checked={on}
                          data-item={item.id}
                          onClick={() => (on ? onDetach(item) : onAttach(item))}
                          className="flex min-h-[34px] w-full items-center gap-[9px] rounded-[8px] px-[6px] text-left hover:bg-sel-bg"
                        >
                          <span className="flex min-w-0 flex-1 flex-col">
                            <span className="truncate text-[13px]">{item.label}</span>
                            {item.detail ? (
                              <span className="truncate text-[11.5px] text-ink-3">
                                {item.detail}
                              </span>
                            ) : null}
                          </span>
                          {on ? (
                            <span
                              data-attached
                              className="flex size-[16px] items-center justify-center rounded-pill bg-green text-on-dark"
                            >
                              <Icon name="check" size={10} />
                            </span>
                          ) : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </Popover>
  );
}
