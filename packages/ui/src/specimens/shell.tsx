import { type JSX, type ReactNode, useState } from "react";
import { HumanAction } from "../attribution/human-action";
import { Button } from "../components/button";
import {
  AppShell,
  FooterAction,
  FooterSpacer,
  Pane,
  PaneAction,
  PortalFooter,
  PortalToolbar,
  RecordHeader,
  type SyncCode,
  Tabsbar,
  Timeline,
  Toolbar,
  type ToolbarProps,
} from "../layout";
import type { Opt } from "../components/tabs";
import { Row, Sheet } from "./frame";
import guards from "../../scope-guards.gen.json";

// A named person: human-only verbs render only through HumanAction (INV-1, F-05-T31).
const PERSON = { kind: "human", name: "Hannah Leclerc" } as const;

// The C-00 Shell kit's specimens (F-05-T18): the Toolbar at 1280, 1400 and 1440 with the DF-39
// fallbacks, every active state, the held states, the PortalToolbar, the RecordHeader in all four
// variants and the seven sync states, the Tabsbar at 50, 44 and 60, Pane and PaneHeader, the
// Timeline, and the AppShell framed for the firm and the portal. The names are the handoff's
// (Brightwater Hale, Ridgeline Property Partners); nothing here is data a screen may use.

const NAV = guards.nav.map((label) => ({ label }));
const FIRM = {
  firm: "Brightwater Hale",
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
} as const;

/** A strip drawn at a stated width, scrolling sideways inside the page when the page is narrower. */
function Strip({
  width,
  room = 0,
  children,
}: {
  width: number;
  /** Space under the strip for a menu or tooltip held open on it (px). */
  room?: number;
  children: ReactNode;
}): JSX.Element {
  return (
    <div style={{ paddingBottom: room + 4 }} className="max-w-full overflow-x-auto">
      <div style={{ width }} className="flex-none rounded-nested bg-shell">
        {children}
      </div>
    </div>
  );
}

function ToolbarAt({
  width,
  room,
  ...props
}: { width: number; room?: number } & Partial<ToolbarProps>): JSX.Element {
  return (
    <Strip width={width} {...(room === undefined ? {} : { room })}>
      <Toolbar nav={NAV} {...FIRM} active="Home" {...props} />
    </Strip>
  );
}

export function ToolbarSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Sheet
        title="Toolbar: the width test (DF-39)"
        meta="46 high · measured at weight 500 · nothing wraps, no type shrinks"
      >
        {[1440, 1400, 1280, 1080].map((width) => (
          <Row
            key={width}
            name={String(width)}
            meaning="Fallbacks apply in order until the nav fits"
          >
            <ToolbarAt width={width} active="Audits" />
          </Row>
        ))}
        <Row name="Step 1" meaning="Firm pill reads Brightwater">
          <ToolbarAt width={1400} minFallback="firm-short" />
        </Row>
        <Row name="Step 2" meaning="Home is the 30px house pill">
          <ToolbarAt width={1400} minFallback="home-pill" />
        </Row>
        <Row name="Step 3" meaning="Signatures in More">
          <ToolbarAt width={1400} minFallback="signatures" active="Signatures" />
        </Row>
        <Row name="Step 4" meaning="Signatures, Closes, Audits in More">
          <ToolbarAt width={1280} minFallback="signatures-closes-audits" active="Audits" />
        </Row>
        <Row name="More open" meaning="The current page has the check">
          <ToolbarAt width={1080} room={230} active="Signatures" forceState={{ moreOpen: true }} />
        </Row>
      </Sheet>
      <Sheet title="Toolbar: every active state" meta="One strip per area, at 1500 so all show">
        {NAV.map((item) => (
          <Row key={item.label} name={item.label}>
            <ToolbarAt width={1500} active={item.label} />
          </Row>
        ))}
      </Sheet>
      <Sheet title="Toolbar: held states and contexts">
        <Row name="Hover" meaning="Audits">
          <ToolbarAt
            width={1500}
            active="Home"
            forceState={{ nav: { label: "Audits", state: "hover" } }}
          />
        </Row>
        <Row name="Focus" meaning="Inbox">
          <ToolbarAt
            width={1500}
            active="Home"
            forceState={{ nav: { label: "Inbox", state: "focus" } }}
          />
        </Row>
        <Row name="Go… pressed">
          <ToolbarAt width={1500} forceState={{ go: "pressed" }} />
        </Row>
        <Row name="Go… tooltip" meaning="Also lists the other ways in">
          <ToolbarAt width={1500} room={64} forceState={{ goTip: true }} />
        </Row>
        <Row name="Bell read" meaning="No dot">
          <ToolbarAt width={1500} unread={false} />
        </Row>
        <Row name="Settings" meaning="No area active, the firm pill pressed">
          <ToolbarAt width={1500} active="" firmPressed />
        </Row>
        <Row name="Support and bell pressed">
          <ToolbarAt width={1500} supportPressed bellPressed />
        </Row>
      </Sheet>
    </div>
  );
}

const PORTAL_NAV = [
  { label: "Home", icon: "house" },
  { label: "Documents", icon: "file-text" },
  { label: "Questions", icon: "circle-help" },
  { label: "Approvals", icon: "circle-check" },
  { label: "Sign", icon: "signature" },
  { label: "Messages", icon: "message-circle" },
  { label: "Deliverables", icon: "download" },
] as const;

export function PortalToolbarSpecimen(): JSX.Element {
  const individual = PORTAL_NAV.filter((item) => item.label !== "Approvals");
  return (
    <div className="flex flex-col gap-3">
      <Sheet title="PortalToolbar" meta="46 high · white-labelled · no Go…, Support or bell">
        <Row name="Documents" meaning="The firm's initials tile">
          <Strip width={1400}>
            <PortalToolbar
              firm="Brightwater Hale"
              user="Jonah Feld"
              nav={PORTAL_NAV}
              active="Documents"
            />
          </Strip>
        </Row>
        <Row name="With a count" meaning="Messages 1">
          <Strip width={1400}>
            <PortalToolbar
              firm="Brightwater Hale"
              user="Jonah Feld"
              nav={PORTAL_NAV.map((item) =>
                item.label === "Messages" ? { ...item, count: 1 } : item,
              )}
              active="Messages"
              mark="wave"
            />
          </Strip>
        </Row>
        <Row name="Individual client" meaning="Approvals is not offered">
          <Strip width={1400}>
            <PortalToolbar
              firm="Brightwater Hale"
              user="Jonah Feld"
              nav={individual}
              active="Home"
            />
          </Strip>
        </Row>
        <Row name="User chip pressed" meaning="Account menu open">
          <Strip width={1400}>
            <PortalToolbar firm="Brightwater Hale" user="Jonah Feld" nav={PORTAL_NAV} userOn />
          </Strip>
        </Row>
        <Row name="Footer" meaning="Secured by, when the firm turns it on">
          <Strip width={1400}>
            <PortalFooter />
          </Strip>
        </Row>
      </Sheet>
    </div>
  );
}

const SYNC: readonly SyncCode[] = [
  "not_yet_exported",
  "ready_for_export",
  "exporting",
  "synced",
  "out_of_sync",
  "import_pending_approval",
  "failed",
];

const CLOSE_TABS: Opt[] = [
  "Overview",
  "Intake",
  "Accounts",
  { label: "Review", count: 9, bad: true },
  "Deliverables",
];

export function RecordHeaderSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Sheet title="RecordHeader: default, 42" meta="Every sync state is the same white chip">
        {SYNC.map((code) => (
          <Row key={code} name={code}>
            <Strip width={1400}>
              <RecordHeader
                title="2025 Form 1065"
                context="Ridgeline Property Partners, LP"
                state="Working"
                sync={code}
                syncDate="Sep 10"
              />
            </Strip>
          </Row>
        ))}
        <Row name="Checkpoints pressed" meaning="Its drawer is open">
          <Strip width={1400}>
            <RecordHeader
              title="2025 Form 1065"
              context="Ridgeline Property Partners, LP"
              state="Working"
              checkpointsPressed
            />
          </Strip>
        </Row>
      </Sheet>
      <Sheet title="RecordHeader: audit, 59" meta="Auto mode switch 36 by 21">
        <Row name="Planning" meaning="Auto mode on">
          <Strip width={1400}>
            <RecordHeader
              variant="audit"
              title="PY2025 Employee Benefit Plan Audit"
              context="BH Audit Methodology · EBP v3"
              state="Planning"
            />
          </Strip>
        </Row>
        <Row name="Auto mode off" meaning="Meta and a methodology chip">
          <Strip width={1400}>
            <RecordHeader
              variant="audit"
              title="PY2025 Employee Benefit Plan Audit"
              state="Fieldwork"
              chip="EBP v3"
              meta="Started 9:24 AM"
              autoMode={false}
            />
          </Strip>
        </Row>
      </Sheet>
      <Sheet title="RecordHeader: close, 42 + 50" meta="The period steps back and wraps">
        <Row name="Close">
          <Strip width={1400}>
            <RecordHeader
              variant="close"
              title="Copperleaf Coffee Roasters, Inc."
              periods={["2026-06", "2026-07", "2026-08"]}
              tabs={CLOSE_TABS}
              activeTab="Overview"
            />
          </Strip>
        </Row>
      </Sheet>
      <Sheet title="RecordHeader: settings, 42" meta="Back, the title, a slot on the right">
        <Row name="Settings" meaning="A slot for Save and its state">
          <Strip width={1400}>
            <RecordHeader
              variant="settings"
              title="Firm settings"
              context="Brightwater Hale LLP"
              right={
                <>
                  <span className="text-dense text-ink-3">Unsaved changes</span>
                  <Button size="md">Save</Button>
                </>
              }
            />
          </Strip>
        </Row>
      </Sheet>
    </div>
  );
}

const RETURN_TABS: Opt[] = [
  "Overview",
  { label: "Intake", count: 7 },
  { label: "Review", count: 38 },
  { label: "Issues", count: 16, bad: true },
  "Activity",
];

export function TabsbarSpecimen(): JSX.Element {
  const [view, setView] = useState("grid");
  return (
    <Sheet title="Tabsbar" meta="50 default · 44 compact (small track) · 60 workbench">
      <Row name="Default" meaning="50, with the view toggle at the right">
        <Strip width={1400}>
          <Tabsbar
            label="Return"
            options={RETURN_TABS}
            active="Overview"
            view={{ view, onView: setView }}
          />
        </Strip>
      </Row>
      <Row name="Compact" meaning="44">
        <Strip width={1400}>
          <Tabsbar
            size="compact"
            label="Library"
            options={["Library", "My Agents"]}
            active="Library"
          />
        </Strip>
      </Row>
      <Row name="Workbench" meaning="60, pulled up 10 under the toolbar">
        <Strip width={1400}>
          <Tabsbar
            size="workbench"
            label="Workbench"
            options={["Sessions", "Agents", "Connect"]}
            active="Sessions"
          />
        </Strip>
      </Row>
    </Sheet>
  );
}

function Body({ height = 220, children }: { height?: number; children: ReactNode }): JSX.Element {
  return (
    <Strip width={1400}>
      <div
        style={{ height }}
        className="flex items-stretch gap-(--gutter-pane) px-(--edge-app) pt-(--gutter-pane) pb-(--edge-app)"
      >
        {children}
      </div>
    </Strip>
  );
}

export function PaneSpecimen(): JSX.Element {
  return (
    <Sheet title="Pane and PaneHeader" meta="Header 46 · radius 12 · e2 · panes 10 apart">
      <Row name="Slots" meaning="Round, picker and icon, left title with pills, meta and footer">
        <Body height={260}>
          <Pane
            width={250}
            title="Sessions"
            right={<PaneAction kind="round" icon="plus" label="New session…" opensDialog />}
          />
          <Pane
            width={275}
            title="Agents"
            left={<PaneAction kind="picker" label="All" />}
            right={<PaneAction kind="icon" icon="download" label="Download" />}
          />
          <Pane
            title="Trial Balance"
            titleAlign="left"
            well
            right={
              <>
                <PaneAction icon="pencil" label="Edit" />
                <HumanAction
                  verb="Sign off"
                  actor={PERSON}
                  icon="check"
                  size="sm"
                  variant="secondary"
                  opensDialog
                />
                <PaneAction icon="file-text" label="Source Docs" />
              </>
            }
          />
          <Pane
            width={250}
            title="Request documents"
            right={<PaneAction kind="meta" label="Draft" />}
            footer={
              <>
                <FooterAction kind="ghost">Cancel</FooterAction>
                <FooterSpacer />
                <FooterAction>Save draft</FooterAction>
                <HumanAction verb="Send" actor={PERSON} variant="primary" size="md" />
              </>
            }
          />
        </Body>
      </Row>
      <Row name="Long title" meaning="Ellipsises before it reaches an action">
        <Body height={120}>
          <Pane
            width={330}
            title="A long pane title that must not run under the action beside it"
            right={<PaneAction kind="icon" icon="ellipsis" label="More" />}
          />
        </Body>
      </Row>
      <Row name="Footer kinds" meaning="Primary, secondary, ghost, destructive">
        <Body height={120}>
          <Pane
            width={420}
            title="Footer"
            footer={
              <>
                <FooterAction kind="destructive">Remove</FooterAction>
                <FooterSpacer />
                <FooterAction kind="ghost">Cancel</FooterAction>
                <FooterAction kind="secondary">Save draft</FooterAction>
                <HumanAction verb="Send" actor={PERSON} variant="primary" size="md" />
              </>
            }
          />
        </Body>
      </Row>
    </Sheet>
  );
}

export function TimelineSpecimen(): JSX.Element {
  return (
    <Sheet title="Timeline" meta="Date 76 · disc column 20 with a hairline · text">
      <Row name="Activity" meaning="One card, a status disc beside every title">
        <div className="w-[380px] rounded-pane bg-shell">
          <Timeline
            label="Activity"
            events={[
              {
                id: "e1",
                date: "Sep 14",
                state: "done",
                title: "Return prepared",
                detail: "Ridgeline Property Partners, LP · 2025 Form 1065",
              },
              {
                id: "e2",
                date: "Sep 12",
                state: "half",
                title: "Documents received",
                detail: "Four of six requested documents are in.",
              },
              { id: "e3", date: "Sep 8", state: "wait", title: "Request sent" },
            ]}
          />
        </div>
      </Row>
    </Sheet>
  );
}

export function AppShellSpecimen(): JSX.Element {
  const [active, setActive] = useState("Audits");
  return (
    <div className="flex flex-col gap-3">
      <Sheet
        title="AppShell: firm, framed"
        meta="1400 window · toolbar 46 · audit bar 59 · tabsbar 50 · panes 330 | 536 | flex"
      >
        <Row name="Framed" meaning="Presentation only; the product fills the viewport">
          <div className="max-w-full overflow-x-auto">
            <AppShell
              embedded
              height={560}
              toolbar={{
                nav: NAV,
                ...FIRM,
                active,
                onNavigate: setActive,
              }}
              record={
                <RecordHeader
                  variant="audit"
                  title="PY2025 Employee Benefit Plan Audit"
                  context="BH Audit Methodology · EBP v3"
                  state="Planning"
                />
              }
              tabs={
                <Tabsbar
                  label="Audit"
                  options={["Overview", "Evidence", "Issues", "Activity"]}
                  active="Overview"
                />
              }
            >
              <Pane width={330} title="Overview" />
              <Pane width={536} title="Overview" />
              <Pane title="Activity">
                <Timeline
                  label="Activity"
                  events={[
                    { id: "a", date: "Sep 14", state: "run", title: "Planning started" },
                    { id: "b", date: "Sep 9", state: "done", title: "Engagement accepted" },
                  ]}
                />
              </Pane>
            </AppShell>
          </div>
        </Row>
        <Row name="Settings context" meaning="No area active, firm pill pressed, subbar 42">
          <div className="max-w-full overflow-x-auto">
            <AppShell
              embedded
              height={360}
              toolbar={{ nav: NAV, ...FIRM, active: "", firmPressed: true }}
              record={
                <RecordHeader
                  variant="settings"
                  title="Firm settings"
                  context="Brightwater Hale LLP"
                />
              }
            >
              <Pane width={240} header={false} />
              <Pane title="General" />
            </AppShell>
          </div>
        </Row>
      </Sheet>
      <Sheet title="AppShell: portal, framed" meta="Portal toolbar 46 · rail 336 · footer when on">
        <Row name="Portal" meaning="Secured by is the only place the Accrued mark appears">
          <div className="max-w-full overflow-x-auto">
            <AppShell
              variant="portal"
              embedded
              height={420}
              securedFooter
              toolbar={{
                firm: "Brightwater Hale",
                user: "Jonah Feld",
                nav: PORTAL_NAV,
                active: "Documents",
              }}
            >
              <Pane width={336} title="To-dos" />
              <Pane title="Documents" />
            </AppShell>
          </div>
        </Row>
      </Sheet>
    </div>
  );
}
