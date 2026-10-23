import { type JSX, type ReactNode, useState } from "react";
import { HumanAction } from "../attribution/human-action";
import { Button } from "../components/button";
import { Fieldset } from "../components/fieldset";
import { ValueRow } from "../components/inputs";
import { StatusDisc } from "../components/status";
import { Checkbox } from "../components/toggles";
import { Icon } from "../icons";
import {
  CommandPalette,
  ConfirmDialog,
  Dialog,
  Drawer,
  DrawerCard,
  FullSheet,
  Popover,
  PopoverSection,
  SheetColumn,
  SheetColumns,
  SheetModal,
  SheetRow,
  Wizard,
  type WizardStep,
  useOverlayLayers,
} from "../overlays";
import { Held, Row, Sheet as Frame } from "./frame";

// A named person: human-only verbs render only through HumanAction (INV-1, F-05-T31).
const PERSON = { kind: "human", name: "Hannah Leclerc" } as const;

// The overlay specimens (O1 to O6, C-22 Modal, C-23 Drawer, C-00 command palette; F-05-T20). Every
// layer is drawn twice: held in place (`forceState="open"`, no scrim, no trap, so the page stays a
// page) inside a frame the size of the artboard, and live, from a button, as the real layer with
// its scrim, trap, Escape and focus return. Sample names are the handoff's: Hannah Leclerc,
// Priya Raman, Kevin Osei, Claire Feld, Ridgeline Property Partners, LP.

/** A frame the held layers sit in: a quiet window the size of the artboard's area. */
function Stage({
  height,
  width,
  children,
}: {
  height: number;
  width?: number;
  children: ReactNode;
}): JSX.Element {
  return (
    <div
      className="relative flex items-start overflow-hidden rounded-pane bg-nested p-[10px]"
      style={{ height, ...(width === undefined ? {} : { width }) }}
    >
      {children}
    </div>
  );
}

function useOpen(): [boolean, () => void, (open: boolean) => void] {
  const [open, set] = useState(false);
  return [
    open,
    () => {
      set(true);
    },
    set,
  ];
}

const noop = (): void => undefined;

// ---- O1 Popover --------------------------------------------------------------------------------

const REVIEWERS = ["Hannah Leclerc", "Priya Raman", "Kevin Osei", "Accrued Agent"];

function AssignList({ current }: { current: string }): JSX.Element {
  return (
    <ul className="flex flex-col gap-[1px]">
      {REVIEWERS.map((name) => (
        <li
          key={name}
          className="flex h-[34px] items-center justify-between rounded-tile px-[10px] text-body hover:bg-nav-fill"
        >
          {name}
          {name === current && <Icon name="check" size={14} />}
        </li>
      ))}
    </ul>
  );
}

export function PopoverSpecimen(): JSX.Element {
  return (
    <Frame
      title="Popover (O1)"
      meta="8px from the trigger · 266 to 462 wide · card or tray · 180ms · Escape closes it and focus returns to the trigger"
    >
      <Row name="Card" meaning="White, radius 12, the pop shadow: Assign to">
        <Popover
          label="Assign to"
          width={266}
          trigger={
            <Button variant="secondary" opensDialog>
              Assign…
            </Button>
          }
        >
          <AssignList current="Kevin Osei" />
        </Popover>
      </Row>
      <Row name="Tray" meaning="Nested tray of radius 15 around white sections of radius 11: New…">
        <Popover
          label="New"
          variant="tray"
          width={266}
          trigger={
            <Button variant="secondary" opensDialog>
              New…
            </Button>
          }
        >
          <PopoverSection>
            <AssignList current="" />
          </PopoverSection>
        </Popover>
      </Row>
      <Row name="Held open" meaning="In place, 8px under the trigger">
        <div className="flex min-h-[250px] flex-wrap items-start gap-[320px]">
          <Held name="card">
            <Popover
              forceState="open"
              label="Assign to, open"
              align="start"
              width={266}
              trigger={<Button variant="secondary">Assign…</Button>}
            >
              <AssignList current="Kevin Osei" />
            </Popover>
          </Held>
          <Held name="tray">
            <Popover
              forceState="open"
              label="New, open"
              variant="tray"
              align="start"
              width={266}
              trigger={<Button variant="secondary">New…</Button>}
            >
              <PopoverSection>
                <AssignList current="Hannah Leclerc" />
              </PopoverSection>
            </Popover>
          </Held>
        </div>
      </Row>
    </Frame>
  );
}

// ---- C-22 Dialog -------------------------------------------------------------------------------

const SEVERITY = [
  { value: "review", label: "Review point" },
  { value: "waiting", label: "Waiting on the client" },
  { value: "action", label: "Action required" },
] as const;

function IssueForm({
  title,
  onTitle,
}: {
  title: string;
  onTitle: (value: string) => void;
}): JSX.Element {
  return (
    <>
      <Fieldset flush className="mb-0">
        <ValueRow
          kind="text"
          label="Title"
          value={title}
          onChange={onTitle}
          placeholder="Required"
        />
        <ValueRow
          kind="select"
          label="Assign to"
          value="Hannah Leclerc"
          options={REVIEWERS.map((n) => ({ value: n, label: n }))}
        />
        <ValueRow kind="select" label="Severity" value="review" options={SEVERITY} />
        <ValueRow kind="info" label="Linked cell">
          <span className="inline-flex h-[26px] items-center rounded-pill bg-card px-[10px] text-cell shadow-e1">
            03 Liabilities!C29
          </span>
        </ValueRow>
      </Fieldset>
      <Fieldset flush className="mb-0">
        <ValueRow
          kind="paragraph"
          label="Note"
          rows={4}
          placeholder="What should the preparer look at?"
        />
      </Fieldset>
    </>
  );
}

function SignOffForm(): JSX.Element {
  const [agreed, setAgreed] = useState(false);
  return (
    <Fieldset flush className="mb-0">
      <ValueRow
        kind="select"
        label="Role"
        value="Reviewer"
        options={["Preparer", "Reviewer"].map((r) => ({ value: r, label: r }))}
      />
      <div className="flex items-start gap-[10px] px-[12px] pt-[11px] pb-[12px] text-para text-ink-2">
        <Checkbox label="I agree" checked={agreed} onChange={setAgreed} className="mt-[1px]" />
        <span>
          I reviewed Service Organizations and the evidence it cites, and I agree with its
          conclusions as Reviewer.
        </span>
      </div>
    </Fieldset>
  );
}

export function DialogSpecimen(): JSX.Element {
  const [size, setSize] = useState<"sm" | "md" | "lg" | "xl" | null>(null);
  const [title, setTitle] = useState("");
  const [agreed, setAgreed] = useState(false);
  return (
    <Frame
      title="Dialog (C-22)"
      meta="sm 420 · md 560 · lg 760 · xl 1140 · radius 14 on the shell · 52 header: close, title, one primary · no footer · scale in 220ms"
    >
      <Row name="Live" meaning="Each size from a button; type in Issue, then Escape for the guard">
        {(["sm", "md", "lg", "xl"] as const).map((s) => (
          <Button
            key={s}
            variant="secondary"
            opensDialog
            onClick={() => {
              setSize(s);
            }}
          >
            {`Open ${s}…`}
          </Button>
        ))}
        <Dialog
          open={size !== null}
          onOpenChange={(open) => {
            if (!open) {
              setSize(null);
              setTitle("");
              setAgreed(false);
            }
          }}
          title={size === "sm" ? "Sign off" : size === "lg" ? "Send request" : "Issue"}
          size={size ?? "md"}
          dirty={size === "md" && title !== ""}
          action={
            size === "md" ? (
              <Button
                disabled={title === ""}
                onClick={() => {
                  setSize(null);
                }}
              >
                Create
              </Button>
            ) : (
              <HumanAction
                verb={size === "sm" ? "Sign off" : "Send"}
                actor={PERSON}
                disabled={size === "sm" ? !agreed : false}
                onClick={() => {
                  setSize(null);
                }}
              />
            )
          }
        >
          {size === "sm" ? (
            <Fieldset flush className="mb-0">
              <div className="flex items-start gap-[10px] px-[12px] pt-[11px] pb-[12px] text-para text-ink-2">
                <Checkbox label="I agree" checked={agreed} onChange={setAgreed} />
                <span>I reviewed Service Organizations and agree with its conclusions.</span>
              </div>
            </Fieldset>
          ) : size === "md" ? (
            <IssueForm title={title} onTitle={setTitle} />
          ) : (
            <Fieldset flush className="mb-0">
              <ValueRow kind="info" label="Client contact">
                Claire Feld
              </ValueRow>
              <ValueRow kind="info" label="Due">
                Sep 30, 2026
              </ValueRow>
            </Fieldset>
          )}
        </Dialog>
      </Row>
      <Row name="Issue · md" meaning="Held in place: the primary waits for a title">
        <Stage height={470} width={620}>
          <Dialog
            forceState="open"
            open={false}
            onOpenChange={noop}
            title="Issue"
            action={<Button disabled>Create</Button>}
          >
            <IssueForm title="" onTitle={noop} />
          </Dialog>
        </Stage>
      </Row>
      <Row name="Sign off · sm" meaning="Held in place: the primary waits for the box">
        <Stage height={250} width={480}>
          <Dialog
            forceState="open"
            open={false}
            onOpenChange={noop}
            title="Sign off"
            size="sm"
            action={<HumanAction verb="Sign off" actor={PERSON} disabled />}
          >
            <SignOffForm />
          </Dialog>
        </Stage>
      </Row>
      <Row
        name="Reject · sm"
        meaning="A destructive primary is white with brick text, never a red fill"
      >
        <Stage height={250} width={480}>
          <Dialog
            forceState="open"
            open={false}
            onOpenChange={noop}
            title="Reject AJE 2"
            size="sm"
            action={
              <Button variant="destructive" disabled>
                Reject
              </Button>
            }
          >
            <div className="flex flex-col gap-[7px] rounded-nested bg-nested p-[12px] shadow-hair">
              <span className="text-dense font-medium">Reason</span>
              <span className="rounded-tile bg-card px-[10px] py-[8px] text-body text-ink-3 shadow-sel">
                Why is this adjusting entry being rejected?
              </span>
              <span className="text-meta text-ink-3">
                Required. It is saved with the decision.
              </span>
            </div>
          </Dialog>
        </Stage>
      </Row>
    </Frame>
  );
}

export function ConfirmDialogSpecimen(): JSX.Element {
  const [open, setOpen, set] = useOpen();
  return (
    <Frame
      title="ConfirmDialog (C-22)"
      meta="alertdialog · no header · title and text in the body · Cancel and the confirm in the footer · Cancel focused first"
    >
      <Row name="Live" meaning="Cancel takes focus; Escape and Cancel close, Delete confirms">
        <Button variant="secondary" opensDialog onClick={setOpen}>
          Delete Schedule 2…
        </Button>
        <ConfirmDialog
          open={open}
          onOpenChange={set}
          title="Delete Schedule 2"
          confirmLabel="Delete"
          onConfirm={noop}
        >
          Schedule 2 and its 14 rows will be removed from the workpaper. Its citations stay in the
          binder.
        </ConfirmDialog>
        <span className="text-meta text-ink-3">{open ? "open" : "closed"}</span>
      </Row>
      <Row name="Delete" meaning="Destructive confirm: white, brick text">
        <Stage height={170} width={470}>
          <ConfirmDialog
            forceState="open"
            open={false}
            onOpenChange={noop}
            title="Delete Schedule 2"
            confirmLabel="Delete"
            onConfirm={noop}
          >
            Schedule 2 and its 14 rows will be removed from the workpaper. Its citations stay in
            the binder.
          </ConfirmDialog>
        </Stage>
      </Row>
      <Row name="Discard changes?" meaning="The same dialog; a dirty layer opens it over itself">
        <Stage height={150} width={470}>
          <ConfirmDialog
            forceState="open"
            open={false}
            onOpenChange={noop}
            title="Discard changes?"
            confirmLabel="Discard"
            cancelLabel="Keep editing"
            onConfirm={noop}
          >
            What you typed in Issue will be lost.
          </ConfirmDialog>
        </Stage>
      </Row>
    </Frame>
  );
}

// ---- O3 Sheet modal ----------------------------------------------------------------------------

function RaiseIssueBody({
  title,
  onTitle,
}: {
  title: string;
  onTitle: (value: string) => void;
}): JSX.Element {
  return (
    <>
      <Fieldset flush className="mb-0">
        <ValueRow
          kind="text"
          label="Title"
          value={title}
          onChange={onTitle}
          placeholder="Required"
        />
        <ValueRow
          kind="select"
          label="Assign to"
          value="Priya Raman"
          options={REVIEWERS.map((n) => ({ value: n, label: n }))}
        />
        <ValueRow kind="select" label="Severity" value="review" options={SEVERITY} />
      </Fieldset>
      <Fieldset flush className="mb-0">
        <ValueRow
          kind="paragraph"
          label="Note"
          rows={3}
          placeholder="What should the preparer look at?"
        />
      </Fieldset>
    </>
  );
}

export function SheetModalSpecimen(): JSX.Element {
  const [open, setOpen, set] = useOpen();
  const [title, setTitle] = useState("");
  return (
    <Frame
      title="SheetModal (O3)"
      meta="500 wide · top 52 to the window's bottom · radius 16 16 0 0 · scrim .28 · 56 header: close, title, Save · rises 24px in 260ms"
    >
      <Row name="Live" meaning="Save waits for a title; a typed title makes the sheet dirty">
        <Button variant="secondary" opensDialog onClick={setOpen}>
          Raise issue…
        </Button>
        <SheetModal
          open={open}
          onOpenChange={(next) => {
            set(next);
            if (!next) setTitle("");
          }}
          title="Raise Issue"
          dirty={title !== ""}
          action={
            <Button
              disabled={title === ""}
              onClick={() => {
                set(false);
                setTitle("");
              }}
            >
              Save
            </Button>
          }
        >
          <RaiseIssueBody title={title} onTitle={setTitle} />
        </SheetModal>
      </Row>
      <Row name="Held" meaning="Save is disabled until there is something to save">
        <Stage height={430} width={540}>
          <div className="relative mx-auto h-[420px] w-[500px] self-end">
            <SheetModal
              forceState="open"
              open={false}
              onOpenChange={noop}
              title="Raise Issue"
              action={<Button disabled>Save</Button>}
            >
              <RaiseIssueBody title="" onTitle={noop} />
            </SheetModal>
          </div>
        </Stage>
      </Row>
    </Frame>
  );
}

// ---- C-23 Drawer -------------------------------------------------------------------------------

const KV: readonly (readonly [string, string])[] = [
  ["Client", "Ridgeline Property Partners, LP"],
  ["Return", "2025 Form 1065"],
  ["Preparer", "Priya Raman"],
  ["Reviewer", "Hannah Leclerc"],
];

function PeekBody(): JSX.Element {
  return (
    <DrawerCard>
      {KV.map(([k, v]) => (
        <div
          key={k}
          className="flex min-h-[33px] items-center justify-between gap-[12px] border-b-[0.5px] border-hair px-[12px] text-body last:border-b-0"
        >
          <span className="text-ink-2">{k}</span>
          <span>{v}</span>
        </div>
      ))}
    </DrawerCard>
  );
}

const ACTIVITY: readonly { when: string; what: string; detail: string }[] = [
  { when: "Sep 14", what: "Return opened", detail: "Hannah Leclerc opened 2025 Form 1065" },
  { when: "Sep 11", what: "Synced", detail: "Ledger synced for Ridgeline Property Partners, LP" },
];

function ActivityBody(): JSX.Element {
  return (
    <DrawerCard className="p-[14px] pb-[4px]">
      {ACTIVITY.map((e) => (
        <div
          key={e.what}
          className="grid grid-cols-[76px_20px_minmax(0,1fr)] gap-[10px] pb-[16px]"
        >
          <span className="pt-[2px] text-right text-meta text-ink-3">{e.when}</span>
          <span className="flex justify-center">
            <StatusDisc state="done" />
          </span>
          <span className="flex flex-col gap-[3px]">
            <b className="text-section leading-[1.3]">{e.what}</b>
            <span className="text-dense text-ink-2">{e.detail}</span>
          </span>
        </div>
      ))}
    </DrawerCard>
  );
}

export function DrawerSpecimen(): JSX.Element {
  const [which, setWhich] = useState<"notifications" | "peek" | "activity" | null>(null);
  const close = (open: boolean): void => {
    if (!open) setWhich(null);
  };
  return (
    <Frame
      title="Drawer (O2, C-23)"
      meta="380, 440 or 560 wide · floats 10px from the edges · radius 14 · header 46: close, title, Open and ··· · slides 24px in 260ms · one at a time"
    >
      <Row
        name="Live"
        meaning="Opening one replaces the other; the peek takes no scrim, trap or focus"
      >
        <Button
          variant="secondary"
          onClick={() => {
            setWhich("notifications");
          }}
        >
          Notifications
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setWhich("peek");
          }}
        >
          Peek a record
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setWhich("activity");
          }}
        >
          Activity
        </Button>
        <Drawer open={which === "notifications"} onOpenChange={close} title="Notifications" bare>
          <DrawerCard>
            <div className="flex min-h-[56px] items-center gap-[11px] px-[12px] text-body">
              <StatusDisc state="wait" />
              <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                <span className="truncate font-medium">Materiality needs your decision</span>
                <span className="truncate text-meta text-ink-3">
                  Northwind Robotics 401(k) Plan · PY2025 · 4 min ago
                </span>
              </span>
            </div>
          </DrawerCard>
        </Drawer>
        <Drawer
          open={which === "peek"}
          onOpenChange={close}
          peek
          title="2025 Form 1065 · Ridgeline"
          onOpen={noop}
          more={[[{ label: "Copy link", onSelect: noop }]]}
          bare
        >
          <PeekBody />
        </Drawer>
        <Drawer open={which === "activity"} onOpenChange={close} title="Activity" size="sm" bare>
          <ActivityBody />
        </Drawer>
      </Row>
      <Row name="Peek · md" meaning="Held: non-modal, no scrim, role complementary, Open and ···">
        <Stage height={330} width={480}>
          <div className="ml-auto h-full">
            <Drawer
              forceState="open"
              open={false}
              onOpenChange={noop}
              peek
              title="2025 Form 1065 · Ridgeline"
              onOpen={noop}
              more={[[{ label: "Copy link", onSelect: noop }]]}
              bare
            >
              <PeekBody />
            </Drawer>
          </div>
        </Stage>
      </Row>
      <Row name="Activity · sm" meaning="Held: modal, 380, a timeline in one card">
        <Stage height={330} width={420}>
          <div className="ml-auto h-full">
            <Drawer
              forceState="open"
              open={false}
              onOpenChange={noop}
              title="Activity"
              size="sm"
              bare
            >
              <ActivityBody />
            </Drawer>
          </div>
        </Stage>
      </Row>
    </Frame>
  );
}

// ---- O4 Full sheet -----------------------------------------------------------------------------

const ALLOCATION: readonly { title: string; rows: readonly (readonly [string, string])[] }[] = [
  {
    title: "Partners",
    rows: [
      ["Calder Family Trust", "40.0%"],
      ["Marrow Point Holdings, LLC", "30.0%"],
      ["Juno Okafor", "30.0%"],
    ],
  },
  {
    title: "Profit",
    rows: [
      ["Ordinary income", "Pro rata"],
      ["Guaranteed payments", "Fixed"],
    ],
  },
  {
    title: "Capital",
    rows: [
      ["Contributions", "Pro rata"],
      ["Distributions", "Pro rata"],
    ],
  },
];

function AllocationBody(): JSX.Element {
  return (
    <SheetColumns>
      {ALLOCATION.map((col) => (
        <SheetColumn key={col.title} title={col.title}>
          {col.rows.map(([k, v]) => (
            <SheetRow key={k} label={k} value={v} />
          ))}
        </SheetColumn>
      ))}
    </SheetColumns>
  );
}

export function FullSheetSpecimen(): JSX.Element {
  const [open, setOpen, set] = useOpen();
  return (
    <Frame
      title="FullSheet (O4)"
      meta="Inset 14, top 60 · radius 14 · scrim .30 · 46 header: title centred, close on the right · three columns of cards · rises 12px"
    >
      <Row name="Live" meaning="Focus starts on the close">
        <Button variant="secondary" opensDialog onClick={setOpen}>
          Allocation structure…
        </Button>
        <FullSheet
          open={open}
          onOpenChange={set}
          title="Allocation structure · Ridgeline Property Partners, LP"
        >
          <AllocationBody />
        </FullSheet>
      </Row>
      <Row name="Held" meaning="In place">
        <Stage height={300} width={920}>
          <div className="h-full w-full">
            <FullSheet
              forceState="open"
              open={false}
              onOpenChange={noop}
              title="Allocation structure · Ridgeline Property Partners, LP"
            >
              <AllocationBody />
            </FullSheet>
          </div>
        </Stage>
      </Row>
    </Frame>
  );
}

// ---- O5 Command palette ------------------------------------------------------------------------

const PALETTE = [
  {
    label: "Jump to",
    items: [
      { id: "nw", label: "Northwind Robotics 401(k) Plan", hint: "Audit · Planning" },
      {
        id: "rl",
        label: "2025 Form 1065 · Ridgeline Property Partners, LP",
        hint: "Tax return · Working",
      },
      { id: "cl", label: "Copperleaf Coffee Roasters, Inc.", hint: "Close · 2026-08" },
    ],
  },
  {
    label: "Go to",
    items: [
      { id: "eng", label: "Engagements", hint: "Page" },
      { id: "tax", label: "Tax Returns", hint: "Page" },
      { id: "inbox", label: "Inbox", hint: "Page" },
    ],
  },
  {
    label: "Actions",
    items: [
      { id: "new", label: "New engagement…", hint: "" },
      { id: "ask", label: "Ask Accrued Agent…", hint: "" },
    ],
  },
];

function filtered(query: string): typeof PALETTE {
  const q = query.trim().toLowerCase();
  return PALETTE.map((g) => ({
    ...g,
    items: g.items.filter((i) => q === "" || i.label.toLowerCase().includes(q)),
  }));
}

export function CommandPaletteSpecimen(): JSX.Element {
  const [open, setOpen, set] = useOpen();
  const [query, setQuery] = useState("");
  const toGroups = (q: string) =>
    filtered(q).map((g) => ({
      label: g.label,
      items: g.items.map((i) => ({
        id: i.id,
        label: i.label,
        ...(i.hint === "" ? {} : { hint: i.hint }),
        icon: <Icon name={g.label === "Go to" ? "arrow-right" : "file-text"} size={14} />,
        run: noop,
      })),
    }));
  return (
    <Frame
      title="CommandPalette (O5)"
      meta="560 wide, 96 from the top · tray radius 15 around a white body · 46 search · 36 rows · footer with the wordmark and key hints · ↑ ↓ stop at the ends"
    >
      <Row name="Live" meaning="Type to filter; ↑ ↓ move, ↵ opens, Escape closes">
        <Button variant="secondary" onClick={setOpen}>
          Go…
        </Button>
        <CommandPalette
          open={open}
          onOpenChange={(next) => {
            set(next);
            if (!next) setQuery("");
          }}
          query={query}
          onQueryChange={setQuery}
          groups={toGroups(query)}
        />
      </Row>
      <Row name="Held" meaning="In place, first row highlighted">
        <Stage height={520} width={600}>
          <CommandPalette
            forceState="open"
            open={false}
            onOpenChange={noop}
            query=""
            onQueryChange={noop}
            groups={toGroups("")}
          />
        </Stage>
      </Row>
      <Row name="No match" meaning="The list says what it was asked for">
        <Stage height={180} width={600}>
          <CommandPalette
            forceState="open"
            open={false}
            onOpenChange={noop}
            query="zzz"
            onQueryChange={noop}
            groups={[]}
          />
        </Stage>
      </Row>
    </Frame>
  );
}

// ---- O6 Wizard ---------------------------------------------------------------------------------

const STEP_LABELS = [
  "Client & type",
  "Standards & methodology",
  "Period & deadlines",
  "Team & independence",
  "Binder & portal",
  "Letter & review",
] as const;

function stepsAt(at: number): WizardStep[] {
  return STEP_LABELS.map((label, i) => ({
    id: String(i),
    label,
    state: i < at ? "done" : i === at ? "current" : "todo",
  }));
}

function StepBody({ at }: { at: number }): JSX.Element {
  return (
    <Fieldset title={STEP_LABELS[at] ?? ""} flush className="mb-0 max-w-[560px]">
      <ValueRow
        kind="select"
        label="Client"
        value="Fairhaven Foods 401(k) Plan"
        options={[{ value: "Fairhaven Foods 401(k) Plan", label: "Fairhaven Foods 401(k) Plan" }]}
      />
      <ValueRow
        kind="select"
        label="Type"
        value="EBP audit"
        options={[{ value: "EBP audit", label: "EBP audit" }]}
      />
    </Fieldset>
  );
}

export function WizardSpecimen(): JSX.Element {
  const [open, setOpen, set] = useOpen();
  const [at, setAt] = useState(0);
  return (
    <Frame
      title="Wizard (O6)"
      meta="The full sheet's frame · 220 step list with discs · 56 sticky footer: Back, Save draft, Next, and Create on the last step · steps are data"
    >
      <Row
        name="Live"
        meaning="Next walks the steps; Create is the last; a done step can be reopened"
      >
        <Button
          variant="secondary"
          opensDialog
          onClick={() => {
            setAt(0);
            setOpen();
          }}
        >
          New engagement…
        </Button>
        <Wizard
          open={open}
          onOpenChange={set}
          title="New engagement"
          subtitle="Draft · saved 9:39 AM"
          steps={stepsAt(at)}
          onStepChange={(id) => {
            setAt(Number(id));
          }}
          onBack={() => {
            setAt((i) => Math.max(0, i - 1));
          }}
          onNext={() => {
            setAt((i) => Math.min(STEP_LABELS.length - 1, i + 1));
          }}
          onSaveDraft={noop}
          onCreate={() => {
            set(false);
          }}
          dirty={at > 0}
        >
          <StepBody at={at} />
        </Wizard>
      </Row>
      <Row name="Step 2" meaning="Held: Back, Save draft and Next">
        <Stage height={400} width={920}>
          <div className="h-full w-full">
            <Wizard
              forceState="open"
              open={false}
              onOpenChange={noop}
              title="New engagement"
              subtitle="Draft · saved 9:39 AM"
              steps={stepsAt(1)}
              onSaveDraft={noop}
            >
              <StepBody at={1} />
            </Wizard>
          </div>
        </Stage>
      </Row>
      <Row name="Last step" meaning="Held: Create">
        <Stage height={400} width={920}>
          <div className="h-full w-full">
            <Wizard
              forceState="open"
              open={false}
              onOpenChange={noop}
              title="New engagement"
              steps={stepsAt(STEP_LABELS.length - 1)}
            >
              <StepBody at={STEP_LABELS.length - 1} />
            </Wizard>
          </div>
        </Stage>
      </Row>
    </Frame>
  );
}

// ---- Stacking ----------------------------------------------------------------------------------

function LayerReadout(): JSX.Element {
  const layers = useOverlayLayers();
  return (
    <span role="status" aria-label="Open layers" className="text-meta text-ink-3">
      {layers.length === 0
        ? "No layer open"
        : `Open, bottom first: ${layers.map((l) => l.kind).join(", ")}`}
    </span>
  );
}

export function OverlayStackingSpecimen(): JSX.Element {
  const [drawer, setDrawer] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [dirtyOpen, setDirtyOpen] = useState(false);
  const [text, setText] = useState("");
  const [which, setWhich] = useState<"a" | "b" | null>(null);
  const [sheet, setSheet] = useState(false);
  const [over, setOver] = useState(false);
  return (
    <Frame
      title="Stacking and the OverlayStack"
      meta="Escape closes the topmost layer only · focus returns to each opener · scroll lock released · a second drawer replaces the first · dirty layers ask first"
    >
      <Row name="Open layers" meaning="The stack, bottom first; z-order follows it">
        <LayerReadout />
      </Row>
      <Row
        name="Popover, dialog, drawer"
        meaning="Escape three times: the popover, then the dialog, then the drawer"
      >
        <Button
          variant="secondary"
          onClick={() => {
            setDrawer(true);
          }}
        >
          Open the request drawer
        </Button>
        <Drawer open={drawer} onOpenChange={setDrawer} title="Request">
          <Button
            variant="secondary"
            opensDialog
            onClick={() => {
              setDialog(true);
            }}
          >
            Assign…
          </Button>
          <Dialog open={dialog} onOpenChange={setDialog} title="Assign to" size="sm">
            <Popover
              label="Reviewers"
              width={266}
              trigger={
                <Button variant="secondary" opensDialog>
                  Reviewers…
                </Button>
              }
            >
              <AssignList current="Hannah Leclerc" />
            </Popover>
          </Dialog>
        </Drawer>
      </Row>
      <Row
        name="Dirty guard"
        meaning="Type, then Escape, the close or the scrim: Discard changes? asks"
      >
        <Button
          variant="secondary"
          opensDialog
          onClick={() => {
            setDirtyOpen(true);
          }}
        >
          Issue…
        </Button>
        <Dialog
          open={dirtyOpen}
          onOpenChange={(open) => {
            setDirtyOpen(open);
            if (!open) setText("");
          }}
          title="Issue"
          dirty={text !== ""}
          action={<Button disabled={text === ""}>Create</Button>}
        >
          <Fieldset flush className="mb-0">
            <ValueRow
              kind="text"
              label="Title"
              value={text}
              onChange={setText}
              placeholder="Required"
            />
          </Fieldset>
        </Dialog>
      </Row>
      <Row name="Never two drawers" meaning="B replaces A; the peek counts as a drawer too">
        <Button
          variant="secondary"
          onClick={() => {
            setWhich("a");
          }}
        >
          Drawer A
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setWhich("b");
          }}
        >
          Drawer B
        </Button>
        <Drawer
          open={which === "a"}
          onOpenChange={(o) => {
            if (!o) setWhich(null);
          }}
          title="Drawer A"
        >
          <p className="text-body">Opening Drawer B closes this one.</p>
        </Drawer>
        <Drawer
          open={which === "b"}
          onOpenChange={(o) => {
            if (!o) setWhich(null);
          }}
          title="Drawer B"
          size="sm"
        >
          <p className="text-body">Opening Drawer A closes this one.</p>
        </Drawer>
      </Row>
      <Row
        name="Modal over a drawer"
        meaning="One drawer and one modal on top; Escape closes the modal first"
      >
        <Button
          variant="secondary"
          onClick={() => {
            setSheet(true);
          }}
        >
          Drawer, then sheet
        </Button>
        <Drawer open={sheet} onOpenChange={setSheet} title="Record">
          <Button
            variant="secondary"
            opensDialog
            onClick={() => {
              setOver(true);
            }}
          >
            Raise issue…
          </Button>
          <SheetModal open={over} onOpenChange={setOver} title="Raise Issue">
            <p className="text-body">The sheet sits over the drawer; its scrim is .28.</p>
          </SheetModal>
        </Drawer>
      </Row>
      <Row
        name="Scrims"
        meaning="Dialog and drawer .22 · agent sheet .28 · full sheet .30, each with saturate .9 and a 0.5px blur"
      >
        {(
          [
            ["dialog", "bg-(--scrim)"],
            ["agent", "bg-(--scrim-agent)"],
            ["sheet", "bg-(--scrim-sheet)"],
          ] as const
        ).map(([name, cls]) => (
          <Held key={name} name={name}>
            <span className="relative flex h-[56px] w-[140px] items-center justify-center overflow-hidden rounded-pane bg-card text-dense text-ink-2 shadow-e1">
              Page
              <span aria-hidden="true" className={`absolute inset-0 ${cls}`} />
            </span>
          </Held>
        ))}
      </Row>
    </Frame>
  );
}
