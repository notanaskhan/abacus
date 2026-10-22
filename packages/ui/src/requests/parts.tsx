import { Check } from "lucide-react";
import {
  type JSX,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
  useEffect,
  useRef,
  useState,
} from "react";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { StatusDisc } from "../components/status";
import { RING_CIRCUMFERENCE, RING_RADIUS, ringView } from "../components/progress-model";
import { Icon, type IconName } from "../icons";
import { useMotion } from "../motion";
import {
  type CategoryKey,
  type CategoryState,
  type DoneButtonView,
  IGNORE_REASONS,
  type RequestCategory,
  type RequestItem,
  type UploadInFlight,
  rowView,
} from "./types";

// C-16 Request kit, portal variant (F-05-T36): the parts. RequestSection, RequestRow (client side),
// CategoryRail, DropZone with its ring, the Uploading band and UploadRow, MarkAsDone, the done
// banner, the empty states, the drag stack and the simple menu the Show, Binder, Ignore and Remove
// menus share. Missing is neutral: a requested item shows "Upload…" and Ignore, never red; red tint
// is only for a returned file and the Trash2 hover. No checkboxes on the client side.

/** A text button under 24 high keeps a 24px target (SC 2.5.8): a pseudo-element 3px past it. */
const LINK_HIT = "relative before:absolute before:inset-x-0 before:-inset-y-[3px]";

// ---- SimpleMenu -------------------------------------------------------------------------------

export interface SimpleMenuItem {
  label: string;
  onSelect: () => void;
  /** A radio menu's current choice: a check and the weight 500. */
  checked?: boolean;
}

export interface SimpleMenuProps {
  open: boolean;
  onClose: () => void;
  /** The trigger, so focus returns to it on close. */
  trigger: RefObject<HTMLElement | null>;
  label: string;
  items: readonly SimpleMenuItem[];
  /** 11.5 ink-3 above the items: "Why are you skipping this?". */
  head?: string;
  /** A pill field under the items (the Ignore note). */
  note?: { value: string; onChange: (value: string) => void; placeholder: string };
  width: number;
  /** Left-aligned to the trigger (the Show menu) or right-aligned (every other). */
  align?: "start" | "end";
  /** Hold open for a specimen: drawn in place, no focus taken, nothing dismisses it. */
  held?: boolean;
}

const MENU_ITEM =
  "flex h-[34px] flex-none items-center justify-between gap-[10px] rounded-tile px-[10px] text-left text-body whitespace-nowrap outline-offset-[-2px] hover:bg-nav-fill focus-visible:bg-nav-fill aria-checked:bg-nav-fill aria-checked:font-medium";

/** The C-16 simple menu: outer nested r15, inner white r11, 34 items; ↑ ↓ move, Escape and an
 * outside press close it, focus goes to the checked (or first) item and back to the trigger. */
export function SimpleMenu({
  open,
  onClose,
  trigger,
  label,
  items,
  head,
  note,
  width,
  align = "end",
  held = false,
}: SimpleMenuProps): JSX.Element | null {
  const box = useRef<HTMLDivElement>(null);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const radio = items.some((i) => i.checked !== undefined);

  useEffect(() => {
    if (!open || held) return undefined;
    const start = Math.max(
      0,
      items.findIndex((i) => i.checked === true),
    );
    refs.current[start]?.focus();
    const outside = (event: MouseEvent): void => {
      const target = event.target as Node;
      if (box.current?.contains(target) === true) return;
      if (trigger.current?.contains(target) === true) return;
      onClose();
    };
    document.addEventListener("mousedown", outside);
    return () => {
      document.removeEventListener("mousedown", outside);
    };
  }, [open, held, items, onClose, trigger]);

  if (!open) return null;

  const close = (): void => {
    onClose();
    trigger.current?.focus();
  };
  const onKey = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const list = refs.current.filter((el): el is HTMLButtonElement => el !== null);
    const at = list.findIndex((el) => el === document.activeElement);
    event.preventDefault();
    const step = event.key === "ArrowDown" ? 1 : -1;
    list[(at + step + list.length) % list.length]?.focus();
  };

  return (
    <div
      ref={box}
      data-part="menu"
      onKeyDown={onKey}
      style={{ width }}
      className={cn(
        "absolute top-[calc(100%+4px)] z-(--z-menu) rounded-menu bg-nested p-[4px] text-left shadow-menu motion-reveal",
        align === "start" ? "left-0" : "right-0",
      )}
    >
      <div className="flex flex-col gap-px rounded-menu-inner bg-card p-[4px]">
        {head !== undefined && (
          <div className="px-[10px] pt-[7px] pb-[5px] text-meta leading-[1.35] whitespace-normal text-ink-3">
            {head}
          </div>
        )}
        {/* The menu holds only its items; the head and the note field sit beside it. */}
        <div role="menu" aria-label={label} className="flex flex-col gap-px">
          {items.map((item, i) => (
            <button
              key={item.label}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              role={radio ? "menuitemradio" : "menuitem"}
              {...(radio ? { "aria-checked": item.checked === true } : {})}
              tabIndex={-1}
              className={MENU_ITEM}
              onClick={() => {
                item.onSelect();
                close();
              }}
            >
              {item.label}
              {item.checked === true && <Icon name="check" size={14} strokeWidth={2} />}
            </button>
          ))}
        </div>
        {note !== undefined && (
          <div className="px-[4px] pt-[4px] pb-[2px]">
            <input
              type="text"
              value={note.value}
              placeholder={note.placeholder}
              aria-label={note.placeholder}
              onChange={(event) => {
                note.onChange(event.target.value);
              }}
              className="h-[30px] w-full rounded-pill bg-nested px-[12px] text-dense inset-ring-[0.5px] inset-ring-hair outline-none placeholder:text-ink-3 focus-visible:inset-ring-stroke"
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Glyphs -----------------------------------------------------------------------------------

/** The 17 document glyph: the sheet filled once something is in, faint while requested. */
export function DocGlyph({ filled }: { filled: boolean }): JSX.Element {
  return (
    <svg
      aria-hidden="true"
      width={17}
      height={17}
      viewBox="0 0 24 24"
      data-doc={filled ? "in" : "open"}
      className="mt-px flex-none stroke-ink-3"
    >
      <path
        d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"
        strokeWidth={1.5}
        strokeLinejoin="round"
        className={filled ? "fill-ink-4" : "fill-hair"}
      />
      <path
        d="M14 2v4a2 2 0 0 0 2 2h4"
        fill="none"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** The 19 olive disc a complete category carries. */
function CompleteDisc(): JSX.Element {
  return (
    <span
      role="img"
      aria-label="Complete"
      className="inline-flex size-[19px] flex-none items-center justify-center rounded-pill bg-green text-on-dark"
    >
      <Check aria-hidden="true" size={10} strokeWidth={1.9} />
    </span>
  );
}

/** The green receipt line: a 13 disc and the words, 12.5/500 green-ink. */
export function ReceiptLine({ children }: { children: ReactNode }): JSX.Element {
  return (
    <span className="flex items-center gap-[6px] text-dense font-medium text-green-ink">
      <StatusDisc state="done" size={13} />
      {children}
    </span>
  );
}

// ---- DropZone and uploads ---------------------------------------------------------------------

/** The 50 ring: an amber arc over a faint track around a 46 circle. The arc is hidden at 0, where
 * a round cap would leave a dot (C-16 README). */
export function DropRing({
  progress,
  icon = "file",
  well = false,
}: {
  progress: number;
  icon?: IconName;
  /** The inner circle on the nested fill (the 390 card) instead of white. */
  well?: boolean;
}): JSX.Element {
  const animate = useMotion();
  const view = ringView(progress);
  return (
    <span
      aria-hidden="true"
      className="relative flex size-[50px] flex-none items-center justify-center"
    >
      <svg viewBox="0 0 50 50" className="absolute inset-0 -rotate-90">
        <circle
          cx={25}
          cy={25}
          r={RING_RADIUS}
          fill="none"
          strokeWidth={2}
          className="stroke-hair"
        />
        {view.arc && (
          <circle
            data-arc="upload"
            cx={25}
            cy={25}
            r={RING_RADIUS}
            fill="none"
            strokeWidth={2}
            strokeLinecap="round"
            strokeDasharray={RING_CIRCUMFERENCE}
            strokeDashoffset={view.offset}
            className={cn(
              "stroke-amber",
              animate && "transition-[stroke-dashoffset] duration-400 ease-out",
            )}
          />
        )}
      </svg>
      <span
        className={cn(
          "inline-flex items-center justify-center rounded-pill text-ink-2",
          well ? "size-[44px] bg-nested" : "size-[46px] bg-card shadow-e1",
        )}
      >
        <Icon name={icon} size={18} />
      </span>
    </span>
  );
}

export interface DropZoneProps {
  /** The average progress of the files in flight, 0 to 1. */
  progress: number;
  onChoose?: () => void;
}

/** The rail's DropZone: a button that opens the file picker; files dropped anywhere sort
 * themselves (C-16 spec 2). */
export function DropZone({ progress, onChoose }: DropZoneProps): JSX.Element {
  return (
    <div className="p-[10px]">
      <button
        type="button"
        aria-label="Upload documents. Drop files here or choose them"
        onClick={onChoose}
        className="flex w-full flex-col items-center rounded-pane bg-nested px-[20px] pt-[20px] pb-[22px] text-center inset-ring-1 inset-ring-hair transition-shadow duration-[180ms] hover:inset-ring-stroke"
      >
        <DropRing progress={progress} />
        <span className="mt-[10px] text-btn-lg font-medium tracking-[-0.01em]">Documents</span>
        <span className="mt-[4px] max-w-[260px] text-dense leading-[1.5] text-ink-2">
          Drop your files and they’ll be automatically sorted into the right categories
        </span>
      </button>
    </div>
  );
}

/** The "Uploading" band and one row per file in flight: a 64 × 3 amber bar. */
export function UploadList({
  uploads,
}: {
  uploads: readonly UploadInFlight[];
}): JSX.Element | null {
  if (uploads.length === 0) return null;
  return (
    <div data-part="uploading">
      <div className="flex h-[31px] items-center bg-nested px-[12px] text-body text-ink-2">
        Uploading
      </div>
      {uploads.map((u) => (
        <UploadRow key={u.name} upload={u} />
      ))}
    </div>
  );
}

export function UploadRow({ upload }: { upload: UploadInFlight }): JSX.Element {
  const pct = Math.round(Math.min(1, Math.max(0, upload.p)) * 100);
  const done = pct >= 100;
  return (
    <div role="status" className="flex items-center gap-[10px] px-[12px] py-[7px] hairline-b">
      <Icon name="file" size={15} className="text-ink-3" />
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="truncate text-body">{upload.name}</span>
        <span className="text-meta text-ink-3">{upload.size}</span>
      </span>
      <span className="relative flex h-[15px] w-[64px] flex-none items-center justify-end">
        <span
          role="progressbar"
          aria-label={upload.name}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          className={cn(
            "absolute top-[6px] left-0 h-[3px] w-[64px] overflow-hidden rounded-[2px] bg-chip transition-opacity duration-[180ms]",
            done && "opacity-0",
          )}
        >
          <span
            className="block h-full rounded-[2px] bg-amber transition-[width] duration-[140ms] ease-linear"
            style={{ width: `${String(pct)}%` }}
          />
        </span>
        {done && <StatusDisc state="done" size={15} />}
      </span>
    </div>
  );
}

// ---- CategoryRail -----------------------------------------------------------------------------

export interface CategoryRailProps {
  categories: readonly RequestCategory[];
  states: Readonly<Record<CategoryKey, CategoryState>>;
  selected: CategoryKey | null;
  /** A click filters the list to the category; a second click clears it. */
  onSelect: (key: CategoryKey | null) => void;
}

/** "Categories" and the nine 39 rows (`listbox`): ↑ ↓ Home End move, Enter or Space picks. */
export function CategoryRail({
  categories,
  states,
  selected,
  onSelect,
}: CategoryRailProps): JSX.Element {
  const refs = useRef<(HTMLDivElement | null)[]>([]);
  const [focus, setFocus] = useState(() =>
    Math.max(
      0,
      categories.findIndex((c) => c.key === selected),
    ),
  );
  const move = (to: number): void => {
    const next = (to + categories.length) % categories.length;
    setFocus(next);
    refs.current[next]?.focus();
  };
  const onKey = (event: KeyboardEvent<HTMLDivElement>, i: number, key: CategoryKey): void => {
    if (event.key === "ArrowDown") move(i + 1);
    else if (event.key === "ArrowUp") move(i - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(categories.length - 1);
    else if (event.key === "Enter" || event.key === " ") onSelect(selected === key ? null : key);
    else return;
    event.preventDefault();
  };
  const selectedAt = categories.findIndex((c) => c.key === selected);
  return (
    <div data-part="categories">
      <div className="px-[12px] pt-[12px] pb-[6px] text-section font-normal tracking-normal text-ink-2">
        Categories
      </div>
      <div role="listbox" aria-label="Categories" className="px-[6px] pb-[10px]">
        {categories.map((c, i) => {
          const state = states[c.key];
          const on = c.key === selected;
          const ruled = i !== 0 && !on && i !== selectedAt + 1;
          return (
            <div
              key={c.key}
              ref={(el) => {
                refs.current[i] = el;
              }}
              role="option"
              aria-selected={on}
              tabIndex={i === focus ? 0 : -1}
              title={state.none ? "Nothing requested" : undefined}
              data-done={state.done ? "true" : "false"}
              onClick={() => {
                setFocus(i);
                onSelect(on ? null : c.key);
              }}
              onKeyDown={(event) => {
                onKey(event, i, c.key);
              }}
              className={cn(
                "flex h-[39px] cursor-pointer items-center gap-[10px] rounded-tile pr-[6px] pl-[8px] text-section font-normal tracking-normal outline-offset-[-2px] transition-colors duration-200 hover:bg-nav-fill",
                ruled && "hairline-t",
                on && "bg-sel-bg font-medium hover:bg-sel-bg",
              )}
            >
              <Icon name={c.icon} size={15} className={state.none ? "text-ink-4" : "text-ink-3"} />
              <span className={cn("min-w-0 flex-1 truncate", state.none && "text-ink-3")}>
                {c.label}
              </span>
              {state.done && <CompleteDisc />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---- RequestSection and RequestRow ------------------------------------------------------------

export function RequestSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: IconName;
  children: ReactNode;
}): JSX.Element {
  return (
    <section role="group" aria-label={title} className="flex-none rounded-pane bg-card shadow-e1">
      <div className="flex min-h-[44px] items-center gap-[10px] px-[14px] text-section">
        <Icon name={icon} size={15} className="text-ink-2" />
        <span className="min-w-0 flex-1">{title}</span>
      </div>
      {children}
    </section>
  );
}

export interface RequestRowProps {
  item: RequestItem;
  /** The firm's name for the accepted and firm-provided lines. */
  firm: string;
  /** Today's date for new lines ("Sep 14"), from the server's clock. */
  today: string;
  /** Force the hover fill (a specimen). */
  hover?: boolean;
  /** Hold the Ignore menu open (TPL-07f). */
  ignoreOpen?: boolean;
  onUpload?: (id: string) => void;
  onIgnore?: (id: string, reason: string, note: string) => void;
  onUndoIgnore?: (id: string) => void;
  onRemove?: (id: string) => void;
  onReply?: (id: string, text: string) => void;
}

/** One request, client side (C-16 spec 6): the document glyph, the title and its lines, and at the
 * end Trash2 on the client's own upload or Ignore on an open request. */
export function RequestRow({
  item,
  firm,
  hover = false,
  ignoreOpen = false,
  onUpload,
  onIgnore,
  onUndoIgnore,
  onRemove,
  onReply,
}: RequestRowProps): JSX.Element {
  const view = rowView(item, firm);
  const [menu, setMenu] = useState<"ignore" | "remove" | null>(ignoreOpen ? "ignore" : null);
  const [note, setNote] = useState("");
  const [replying, setReplying] = useState(false);
  const [reply, setReply] = useState("");
  const ignoreRef = useRef<HTMLButtonElement>(null);
  const trashRef = useRef<HTMLButtonElement>(null);
  const replyRef = useRef<HTMLTextAreaElement>(null);
  // The composer opens on the person's own click, so it takes focus.
  useEffect(() => {
    if (replying) replyRef.current?.focus();
  }, [replying]);
  const open = item.st === "req" || item.st === "fu" || item.st === "ret";
  const sendReply = (): void => {
    if (reply.trim() === "") return;
    onReply?.(item.id, reply.trim());
    setReply("");
    setReplying(false);
  };
  return (
    <div
      data-request={item.id}
      data-status={item.st}
      {...(open ? { "data-open-request": "" } : {})}
      className={cn(
        "flex items-start gap-[12px] bg-card px-[14px] py-[12px] transition-colors duration-200 hairline-t last:rounded-b-pane hover:bg-band-hd",
        hover && "bg-band-hd",
        // An open menu paints over the sections after this one (they are not clipped, so it can).
        menu !== null && "relative z-(--z-menu)",
      )}
    >
      <DocGlyph filled={view.docFilled} />
      <div className="flex min-w-0 flex-1 flex-col gap-[4px]">
        <span
          className={cn(
            "text-section leading-[1.3] tracking-normal [overflow-wrap:anywhere]",
            view.titleMuted && "text-ink-3",
          )}
        >
          {item.title}
        </span>
        {view.fileLines.map((f) => (
          <span key={f} className="truncate text-dense text-ink-2">
            {f}
          </span>
        ))}
        {view.uploaded !== null && <ReceiptLine>{view.uploaded}</ReceiptLine>}
        {view.matched && <span className="text-meta text-ink-3">Matched to this request</span>}
        {view.accepted !== null && <ReceiptLine>{view.accepted}</ReceiptLine>}
        {view.firmProvided !== null && (
          <span className="flex items-start gap-[6px] text-dense leading-[1.45] text-ink-2">
            <Icon name="info" size={13} className="mt-px text-ink-3" />
            {view.firmProvided}
          </span>
        )}
        {view.followUp !== null && (
          <span className="flex flex-col items-start gap-[5px]">
            <span className="inline-flex h-[21px] items-center rounded-pill bg-amber-tint px-[8px] text-pill text-amber-ink">
              Needs follow-up
            </span>
            <span className="max-w-full truncate text-dense leading-[1.4] text-ink-2">
              {view.followUp.note}
            </span>
            {view.followUp.replied !== null && (
              <span className="flex items-center gap-[6px] text-dense text-ink-2">
                <Icon name="reply" size={13} />
                {view.followUp.replied}
              </span>
            )}
            {view.followUp.reply && !replying && (
              <button
                type="button"
                className={cn("text-body font-medium text-espresso hover:underline", LINK_HIT)}
                onClick={() => {
                  setReplying(true);
                }}
              >
                Reply…
              </button>
            )}
            {replying && (
              <span className="flex w-full items-end gap-[8px]">
                <textarea
                  rows={2}
                  value={reply}
                  placeholder="Write your reply"
                  aria-label={`Reply to ${firm}`}
                  ref={replyRef}
                  onChange={(event) => {
                    setReply(event.target.value);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      event.preventDefault();
                      setReplying(false);
                    } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                      event.preventDefault();
                      sendReply();
                    }
                  }}
                  className="min-w-0 flex-1 resize-none rounded-tile bg-card px-[10px] py-[7px] text-body leading-[1.45] inset-ring-[0.5px] inset-ring-stroke outline-none placeholder:text-ink-3"
                />
                <button
                  type="button"
                  disabled={reply.trim() === ""}
                  onClick={sendReply}
                  className="h-[28px] flex-none rounded-pill bg-espresso px-[12px] text-dense font-medium text-on-dark disabled:bg-nested disabled:text-ink-4"
                >
                  Send
                </button>
              </span>
            )}
          </span>
        )}
        {view.returned !== null && (
          <span className="flex flex-col items-start gap-[5px]">
            <span className="inline-flex h-[21px] items-center rounded-pill bg-red-tint px-[8px] text-pill text-red-ink">
              {view.returned.label}
            </span>
            <span className="text-dense leading-[1.45] text-ink-2">{view.returned.note}</span>
          </span>
        )}
        {view.notApplicable !== null && (
          <span className="flex items-center gap-[8px] text-dense text-ink-3">
            {view.notApplicable}
            <button
              type="button"
              className={cn("font-medium text-espresso hover:underline", LINK_HIT)}
              onClick={() => onUndoIgnore?.(item.id)}
            >
              Undo
            </button>
          </span>
        )}
        {(view.uploadLink || item.st === "ret") && (
          <button
            type="button"
            className={cn(
              "self-start text-body font-medium text-espresso hover:underline",
              LINK_HIT,
            )}
            onClick={() => onUpload?.(item.id)}
          >
            Upload…
          </button>
        )}
        {view.uploadLink && item.uploading !== undefined && (
          <span className="text-dense text-ink-3">{item.uploading}</span>
        )}
      </div>
      {(view.trash || view.ignore) && (
        <div className="relative flex flex-none items-center gap-[10px]">
          {view.trash && (
            <button
              ref={trashRef}
              type="button"
              aria-label={`Remove ${view.fileLines[0] ?? item.title}`}
              aria-haspopup="menu"
              aria-expanded={menu === "remove"}
              className={cn(
                "inline-flex size-[26px] items-center justify-center rounded-pill text-ink-3 hover:bg-red-tint hover:text-red-ink aria-expanded:bg-red-tint aria-expanded:text-red-ink",
                PRESS,
              )}
              onClick={() => {
                setMenu(menu === "remove" ? null : "remove");
              }}
            >
              <Icon name="trash-2" size={14} />
            </button>
          )}
          {view.ignore && (
            <button
              ref={ignoreRef}
              type="button"
              aria-label={`Ignore ${item.title}`}
              aria-haspopup="menu"
              aria-expanded={menu === "ignore"}
              className={cn(
                "h-[24px] rounded-pill bg-card px-[10px] text-pill font-normal whitespace-nowrap shadow-e1 hover:bg-nav-fill aria-expanded:bg-nav-fill",
                PRESS,
              )}
              onClick={() => {
                setMenu(menu === "ignore" ? null : "ignore");
              }}
            >
              Ignore
            </button>
          )}
          <SimpleMenu
            open={menu === "ignore"}
            held={ignoreOpen && menu === "ignore"}
            onClose={() => {
              setMenu(null);
            }}
            trigger={ignoreRef}
            label="Ignore"
            head="Why are you skipping this?"
            width={266}
            items={IGNORE_REASONS.map((reason) => ({
              label: reason,
              onSelect: () => onIgnore?.(item.id, reason, note.trim()),
            }))}
            note={{ value: note, onChange: setNote, placeholder: "Add a note (optional)" }}
          />
          <SimpleMenu
            open={menu === "remove"}
            onClose={() => {
              setMenu(null);
            }}
            trigger={trashRef}
            label="Remove"
            head={`Remove this file? ${firm} will no longer see it.`}
            width={266}
            items={[
              { label: "Remove file", onSelect: () => onRemove?.(item.id) },
              { label: "Keep it", onSelect: () => undefined },
            ]}
          />
        </div>
      )}
    </div>
  );
}

// ---- Header actions, banner, empty, drag ------------------------------------------------------

/** Mark as Done: tonal (chip, ink-2) until every request is in, then olive over 260ms. Never
 * `disabled`: `aria-disabled` while blocked, so a click can still say what is open. */
export function MarkAsDone({
  view,
  onClick,
}: {
  view: DoneButtonView;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      aria-disabled={view.ariaDisabled}
      title={view.tip}
      data-ready={view.ready ? "true" : "false"}
      onClick={onClick}
      className={cn(
        "inline-flex h-[30px] flex-none items-center gap-[6px] rounded-pill pr-[13px] pl-[11px] text-body font-medium whitespace-nowrap transition-[background-color,color,box-shadow] duration-[260ms] ease-in-out",
        view.ready ? "bg-green text-on-dark shadow-lift" : "bg-chip text-ink-2",
        PRESS,
      )}
    >
      <Icon name="check" size={13} strokeWidth={2} />
      {view.label}
    </button>
  );
}

/** "Marked done Sep 14 · Brightwater Hale will review your documents", with Undo. */
export function DoneBanner({
  today,
  firm,
  onUndo,
}: {
  today: string;
  firm: string;
  onUndo?: () => void;
}): JSX.Element {
  return (
    <div
      role="status"
      className="flex min-h-[40px] flex-none items-center gap-[8px] rounded-pane bg-green-tint px-[14px] text-body font-medium text-green-ink"
    >
      <Icon name="check" size={14} strokeWidth={2} />
      <span className="min-w-0 flex-1">{`Marked done ${today} · ${firm} will review your documents`}</span>
      {onUndo !== undefined && (
        <button
          type="button"
          onClick={onUndo}
          className="h-[26px] flex-none rounded-pill px-[10px] text-dense font-medium hover:bg-green/12"
        >
          Undo
        </button>
      )}
    </div>
  );
}

export type RequestEmptyKind = "none" | "fu" | "other";

/** The well's empty states (C-16 spec 5). */
export function RequestEmpty({
  kind,
  firm,
}: {
  kind: RequestEmptyKind;
  firm: string;
}): JSX.Element {
  const copy =
    kind === "none"
      ? { title: "You’re all caught up.", text: `${firm} hasn’t requested anything new.` }
      : kind === "fu"
        ? {
            title: "Nothing needs follow-up",
            text: "When your firm asks about a document, it shows up here.",
          }
        : { title: "Nothing here", text: "Try another filter or category." };
  return (
    <div className="flex min-h-[260px] flex-1 flex-col items-center justify-center gap-[6px] p-[24px] text-center">
      <span className="mb-[6px] inline-flex size-[34px] items-center justify-center rounded-tile-lg bg-nested text-ink-2">
        <Icon name="check" size={17} />
      </span>
      <span className="text-btn-lg font-medium tracking-[-0.01em]">{copy.title}</span>
      <span className="max-w-[340px] text-dense leading-[1.45] text-ink-2">{copy.text}</span>
    </div>
  );
}

const STACK = [
  { top: "top-[8px]", turn: "-translate-x-[10px] -rotate-[4.5deg]" },
  { top: "top-[20px]", turn: "translate-x-[10px] rotate-[2.5deg]" },
  { top: "top-[34px]", turn: "" },
] as const;

/** Files over the well: a fanned stack of up to three pills with the count, and the hint pill.
 * Browsers expose no names during a drag, so the pills read "File" unless names are given. */
export function DragStack({
  count,
  names = [],
}: {
  count: number;
  names?: readonly string[];
}): JSX.Element {
  return (
    <>
      <div
        aria-hidden="true"
        data-part="drag-stack"
        className="pointer-events-none absolute inset-x-0 top-0 bottom-0 z-(--z-pop) flex items-center justify-center"
      >
        <div className="relative h-[84px] w-[300px]">
          {STACK.slice(0, Math.min(3, Math.max(1, count))).map((pill, i) => (
            <span
              key={pill.top}
              className={cn(
                "absolute left-[30px] flex h-[34px] w-[240px] items-center gap-[8px] rounded-pill bg-card pr-[14px] pl-[11px] text-dense whitespace-nowrap shadow-pop",
                pill.top,
                pill.turn,
              )}
            >
              <Icon name="file-text" size={14} className="text-ink-3" />
              <span className="min-w-0 truncate">{names[i] ?? "File"}</span>
            </span>
          ))}
          <span className="absolute top-[14px] right-[22px] inline-flex h-[20px] min-w-[20px] items-center justify-center rounded-pill bg-espresso px-[6px] text-meta font-medium text-on-dark">
            {count}
          </span>
        </div>
      </div>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 z-(--z-pop) flex justify-center pb-[24px]"
      >
        <span className="inline-flex h-[30px] items-center gap-[6px] rounded-pill bg-espresso pr-[13px] pl-[11px] text-dense font-medium text-on-dark shadow-pop">
          <Icon name="upload" size={13} />
          Drop to sort into your binder
        </span>
      </div>
    </>
  );
}
