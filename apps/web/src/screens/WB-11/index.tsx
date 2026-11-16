import { Button, Drawer, DrawerCard } from "@abacus/ui";
import { type JSX, useState } from "react";

// WB-11 Integration detail drawer (W-01-T16, W-01-T17; handoff WB-11): the O2 480 drawer in
// fixture mode, every word from the handoff. a connected firm token, b personal consent, c needs
// reauth, d client ledger (QuickBooks Online), e disconnect confirm (typed name), f non-admin.
// Disconnect stays disabled until "CCH Axcess Tax" is typed exactly; no control here connects a
// client's ledger.

export const WB11_SCENARIOS = ["a", "b", "c", "d", "e", "f"] as const;
type Scenario = (typeof WB11_SCENARIOS)[number];
export const DISCONNECT_NAME = "CCH Axcess Tax";

const KV_A = [
  ["Auth mode", "Firm connection · access token"],
  ["Connected by", "Felix Andersen · Jan 14, 2026 9:12 AM"],
  ["Token renews", "Oct 12, 2026"],
  ["Last sync", "Today 9:02 AM"],
  ["Returns linked", "224 (TY2025)"],
  ["Return ID format", "2025I:FeldJ:V3"],
] as const;
const AGENTS = [
  "Season Progress Reporter",
  "Return Drafter",
  "Return Review Packet",
  "Notice Intake & Response Drafter",
  "K-1 Reconciliation Workpaper",
] as const;
const EVENTS = [
  ["Sep 14 9:02 AM", "Synced"],
  ["Sep 11 4:18 PM", "Export complete — 2025 Form 1065 · Harborview Dental Properties, LP"],
  ["Sep 10 3:06 PM", "Synced — 2025 Form 1040 · Jonah & Claire Feld"],
  ["Aug 17 9:58 AM", "Reconnected by Felix Andersen"],
  ["Aug 17 9:00 AM", "Token expired — 1 scheduled run failed (Season Progress Reporter)"],
] as const;
const CLIENTS = [
  ["Copperleaf Coffee Roasters, Inc.", "Connected by Tess Moreno (client) · Jul 2, 2026"],
  ["Ridgeline Property Partners, LP", "Connected by Owen Calder (client)"],
] as const;

function Kv({ rows }: { rows: readonly (readonly [string, string])[] }): JSX.Element {
  return (
    <dl>
      {rows.map(([k, v]) => (
        <div key={k} className="flex h-[33px] items-center justify-between">
          <dt className="text-ink-2">{k}</dt>
          <dd className="font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function DisconnectConfirm({ onConfirm }: { onConfirm: () => void }): JSX.Element {
  const [typed, setTyped] = useState("");
  return (
    <section role="dialog" aria-label={`Disconnect ${DISCONNECT_NAME}?`}>
      <h2>Disconnect {DISCONNECT_NAME}?</h2>
      <p>
        5 agents stop working and 224 returns stop syncing. Return data already in Accrued is kept.
      </p>
      <label>
        Type {DISCONNECT_NAME}
        <input
          value={typed}
          onChange={(e) => {
            setTyped(e.target.value);
          }}
        />
      </label>
      <Button variant="destructive" disabled={typed !== DISCONNECT_NAME} onClick={onConfirm}>
        Disconnect
      </Button>
    </section>
  );
}

export function IntegrationDrawer({ st }: { st?: string | undefined }): JSX.Element {
  const scenario: Scenario = (WB11_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Scenario)
    : "a";
  const [open, setOpen] = useState(true);
  if (scenario === "b") {
    return (
      <div data-screen="WB-11" data-scenario="b">
        <Drawer
          open={open}
          onOpenChange={setOpen}
          title="Google Workspace"
          width={480}
          forceState="open"
          bare
        >
          <DrawerCard>
            <p>Google Workspace will let Accrued, acting as Hannah Leclerc:</p>
            <ul>
              <li>Read Drive files you open in Accrued</li>
              <li>Read Gmail threads you file to a client</li>
              <li>Read your calendar</li>
            </ul>
            <p>
              Accrued will never: send mail, delete files, or share files outside Brightwater Hale.
            </p>
            <Button variant="secondary">Cancel</Button>
            <Button>Continue to Google</Button>
          </DrawerCard>
        </Drawer>
      </div>
    );
  }
  const ledger = scenario === "d";
  const reauth = scenario === "c";
  const admin = scenario !== "f";
  return (
    <div data-screen="WB-11" data-scenario={scenario}>
      <Drawer
        open={open}
        onOpenChange={setOpen}
        title={ledger ? "QuickBooks Online" : "CCH Axcess Tax"}
        width={480}
        forceState="open"
        bare
        meta={<span data-pill>{reauth ? "Needs reauth" : "✓ Connected"}</span>}
        footer={
          admin ? (
            <Button>{reauth ? "Reconnect…" : "Configure mappings…"}</Button>
          ) : (
            <p className="text-[11.5px] text-ink-3">
              Felix Andersen manages this firm connection.
            </p>
          )
        }
      >
        <DrawerCard aria-label="Connection">
          <Kv
            rows={
              ledger ? [["Auth mode", "Firm app · each client authorizes its own company"]] : KV_A
            }
          />
        </DrawerCard>
        {ledger ? (
          <DrawerCard aria-label="Recently synced client companies">
            {CLIENTS.map(([name, by]) => (
              <div key={name} data-client-company>
                <span>{name}</span> <span className="text-ink-3">{by}</span>
              </div>
            ))}
            <p className="text-[12.5px] text-ink-2">
              Clients connect and disconnect their ledgers in their portal. To ask for a reconnect,
              open the close (GL sync).
            </p>
          </DrawerCard>
        ) : (
          <>
            <DrawerCard aria-label="What Accrued may do">
              <p>Never — E-file or change a return's status in CCH Axcess</p>
            </DrawerCard>
            <DrawerCard aria-label="Health">
              <p>
                {reauth
                  ? "Token expired at 9:00 AM · 1 run failed · 5 agents paused"
                  : "Synced · today 9:02 AM · 0 errors"}
              </p>
              <ol>
                {EVENTS.map(([at, text]) => (
                  <li key={at}>
                    <span className="text-ink-3">{at}</span> {text}
                  </li>
                ))}
              </ol>
            </DrawerCard>
            <DrawerCard aria-label={`Agents using it · ${String(AGENTS.length)}`}>
              <ul>
                {AGENTS.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </DrawerCard>
            <DrawerCard aria-label="Who can use it">
              <p>Everyone at Brightwater Hale with access to the return</p>
              <p className="text-[11.5px] text-ink-3">
                Agents read only the returns the person running them can open.
              </p>
            </DrawerCard>
          </>
        )}
        {scenario === "e" && <DisconnectConfirm onConfirm={() => undefined} />}
      </Drawer>
    </div>
  );
}
