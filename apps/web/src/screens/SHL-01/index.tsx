import { AppShell, Pane, Toolbar, type ToolbarForceState } from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { useSession } from "../../app-core/session";
import { MANIFEST, type ScreenEntry } from "../../routes/manifest";
import { AREAS, type ToolbarContext } from "../../app-core/nav-areas";
import { useFirmToolbar } from "../../shell/firm/ToolbarData";
import { PANE_TITLE, R2_LABELS, SETTINGS_PATH, WIDTHS } from "./copy";
import type { Shl01State } from "./scenarios";

// SHL-01 · Firm app shell, toolbar and nav (P-01-T02). The toolbar is chrome over every firm
// screen (legacy/Layout.tsx mounts it through useFirmToolbar); this is its artboard, as fixture
// mode and the gallery draw it. Each strip runs the same data path as the app: the lit item comes
// from where the strip is (a screen ID or a route, through the manifest's `navArea`), the dot from
// `unread_count`, the firm from /v1/me. Nothing here is told which item to light.
//
//   a  the toolbar over an empty T2 body: Home lit, the dot (`unread_count` 4), Go…/⌘K, G-chords
//   b  thirteen 1400 strips, one per landing screen, HOME-01 … SIG-01
//   c  held: hover on Audits, focus-visible on Inbox, Go… pressed
//   d  the bell read (`unread_count` 0)
//   e  the width test, 1400 and 1279, DF-39 with More first
//   f  the settings context: /settings/general, nothing lit, the firm pill pressed
//   g  R2: eight new screens light the item that owns them; the Go… tooltip

/** The toolbar's place on a screen: its ID and its manifest entry's `navArea` (AC 1.1.2). */
export function on(screen: string): ToolbarContext {
  const entry = (MANIFEST as Readonly<Record<string, ScreenEntry>>)[screen];
  return { screen, navArea: entry?.navArea };
}

function useFirmName(): string {
  return useSession().tenant?.firm_name ?? "";
}

function Strip({
  label,
  at,
  width = 1400,
  room = 0,
  forceState,
}: {
  label?: string;
  at: ToolbarContext;
  width?: number;
  /** Space under the strip for a menu or tooltip held open on it. */
  room?: number;
  forceState?: ToolbarForceState;
}): JSX.Element {
  const firm = useFirmName();
  const { toolbar } = useFirmToolbar({
    at,
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div
      data-strip={label ?? ""}
      style={{ paddingBottom: room }}
      className="flex items-center gap-3"
    >
      {label !== undefined && (
        <span className="w-[200px] flex-none text-meta text-ink-3">{label}</span>
      )}
      <div style={{ width }} className="flex-none overflow-hidden rounded-nested bg-shell">
        <Toolbar {...toolbar} {...(forceState === undefined ? {} : { forceState })} />
      </div>
    </div>
  );
}

function Strips({ state, children }: { state: string; children: ReactNode }): JSX.Element {
  return (
    <div data-artboard={state} className="flex flex-col gap-3 overflow-x-auto p-4">
      {children}
    </div>
  );
}

/** Frame a: the live toolbar over an empty T2 body. Routing stays inside the artboard. */
function Default(): JSX.Element {
  const firm = useFirmName();
  const [pathname, setPathname] = useState("/");
  const bar = useFirmToolbar({ at: { pathname }, firm, navigate: setPathname });
  return (
    <div data-artboard="a" data-path={pathname}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <Pane width={330} title={PANE_TITLE} />
        <Pane title={PANE_TITLE} />
      </AppShell>
    </div>
  );
}

export function SHL01({ state = "a" }: { state?: Shl01State }): JSX.Element {
  switch (state) {
    case "a":
      return <Default />;
    case "b":
      return (
        <Strips state="b">
          {AREAS.map((area) => (
            <Strip key={area.landing} label={area.landing} at={on(area.landing)} />
          ))}
        </Strips>
      );
    case "c":
      return (
        <Strips state="c">
          <Strip at={on("HOME-01")} forceState={{ nav: { label: "Audits", state: "hover" } }} />
          <Strip at={on("HOME-01")} forceState={{ nav: { label: "Inbox", state: "focus" } }} />
          <Strip at={on("HOME-01")} forceState={{ go: "pressed" }} />
        </Strips>
      );
    case "d":
      return (
        <Strips state="d">
          <Strip at={on("HOME-01")} />
        </Strips>
      );
    case "e":
      return (
        <Strips state="e">
          {WIDTHS.map((width) => (
            <Strip key={width} label={String(width)} width={width} at={on("HOME-01")} />
          ))}
          <Strip
            label={String(WIDTHS[1])}
            width={WIDTHS[1]}
            room={150}
            at={on("AUD-01")}
            forceState={{ moreOpen: true }}
          />
        </Strips>
      );
    case "f":
      return (
        <Strips state="f">
          <Strip label={SETTINGS_PATH} at={{ pathname: SETTINGS_PATH }} />
        </Strips>
      );
    case "g":
      return (
        <Strips state="g">
          {Object.entries(R2_LABELS).map(([id, label]) => (
            <Strip key={id} label={label} at={on(id)} />
          ))}
          <Strip at={on("HOME-01")} room={64} forceState={{ goTip: true }} />
        </Strips>
      );
  }
}
