import type { ConfirmationDetailOut } from "@abacus/api-client";
import {
  AgentText,
  Amount,
  Button,
  Drawer,
  DrawerCard,
  Label,
  Picker,
  Pill,
  SheetModal,
} from "@abacus/ui";
import { type JSX, useId, useState } from "react";
import { FIELDWORK_COPY } from "./copy";

// ConfirmationDrawer and NewConfirmationSheet (A-08-T26; AUD-14 d, e; AU-C 505). The drawer
// shows the response, the reconciliation (the server's unreconciled figure and classification),
// and why the agent surfaced it; Accept reconciliation renders only when the server allows it (the
// manager). The new sheet's Send stays disabled with the red helper until the address was verified
// from a source other than the client (409 `address_not_verified` is the server's own gate).

const C = FIELDWORK_COPY.confirmations;

export function ConfirmationDrawer({
  open,
  onOpenChange,
  detail,
  why,
  onAccept,
  held,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  detail: ConfirmationDetailOut;
  /** The agent's reason the item surfaced (rendered through AgentText). */
  why?: string | undefined;
  onAccept?: () => void;
  held?: boolean;
}): JSX.Element {
  const row = detail.row;
  const recon = detail.reconciliation;
  const canAccept = row.allowed_actions.includes("confirmation.accept_reconciliation");
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={`${row.number} · ${row.respondent_org}`}
      size="md"
      {...(held === true ? { forceState: "open" as const } : {})}
      footer={
        canAccept && recon !== null && recon.accepted_at === null ? (
          <Button variant="primary" onClick={onAccept}>
            {C.accept}
          </Button>
        ) : undefined
      }
    >
      <div data-fieldwork="confirmation-drawer">
        <DrawerCard>
          <h3 className="px-[14px] pt-[10px] text-[13px] font-medium">{C.response}</h3>
          {detail.response === null ? (
            <p className="px-[14px] py-[10px] text-cell text-ink-3">{C.noResponse}</p>
          ) : (
            <p className="flex items-center gap-[8px] px-[14px] py-[10px] text-cell">
              <Pill
                variant={detail.response.agrees ? "green-tint" : "amber"}
                check={detail.response.agrees}
              >
                {detail.response.agrees ? C.agrees : C.differs}
              </Pill>
              <span className="text-ink-2">{detail.response.respondent_name}</span>
            </p>
          )}
        </DrawerCard>
        {recon !== null && (
          <DrawerCard>
            <h3 className="px-[14px] pt-[10px] text-[13px] font-medium">{C.reconciliation}</h3>
            <dl className="grid grid-cols-[1fr_auto] gap-y-[6px] px-[14px] py-[10px] text-cell">
              <dt className="text-ink-2">{C.book}</dt>
              <dd className="text-right">
                <Amount value={recon.balance_per_books} />
              </dd>
              {recon.items.map((item) => (
                <div key={item.id} data-reconciling={item.id} className="contents">
                  <dt className="text-ink-2">{item.description}</dt>
                  <dd className="text-right">
                    <Amount value={item.amount} />
                  </dd>
                </div>
              ))}
              <dt className="text-ink-2">{C.confirmed}</dt>
              <dd className="text-right">
                <Amount value={recon.balance_per_respondent} />
              </dd>
              <dt className="text-ink-2">{C.unreconciled}</dt>
              <dd className="text-right" data-unreconciled={recon.unreconciled}>
                <Amount value={recon.unreconciled} zero="explicit" />
              </dd>
              {recon.classification !== null && (
                <>
                  <dt className="text-ink-2">{C.classification}</dt>
                  <dd className="text-right capitalize">{recon.classification}</dd>
                </>
              )}
            </dl>
          </DrawerCard>
        )}
        {why !== undefined && (
          <DrawerCard>
            <h3 className="px-[14px] pt-[10px] text-[13px] font-medium">{C.why}</h3>
            <div className="px-[14px] py-[10px] text-cell text-ink-2">
              <AgentText text={why} />
            </div>
          </DrawerCard>
        )}
      </div>
    </Drawer>
  );
}

export type AddressSource = keyof typeof C.sourceNames;
const INDEPENDENT: ReadonlySet<AddressSource> = new Set([
  "prior_year",
  "website",
  "phone",
  "public_register",
  "bank_published",
]); // the server's CHECK decides; this only drives the helper

export interface NewConfirmationDraft {
  type: keyof typeof C.types;
  respondentOrg: string;
  respondentName: string;
  address: string;
  method: string;
  sources: AddressSource[];
}

export function NewConfirmationSheet({
  open,
  onOpenChange,
  onSend,
  initial,
  held,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSend?: (draft: NewConfirmationDraft) => void;
  initial?: Partial<NewConfirmationDraft>;
  held?: boolean;
}): JSX.Element {
  const [draft, setDraft] = useState<NewConfirmationDraft>({
    type: "accounts_receivable",
    respondentOrg: "",
    respondentName: "",
    address: "",
    method: "",
    sources: [],
    ...initial,
  });
  const ids = {
    type: useId(),
    org: useId(),
    name: useId(),
    address: useId(),
    method: useId(),
    help: useId(),
  };
  const independent = draft.sources.some((s) => INDEPENDENT.has(s));
  const complete =
    draft.respondentOrg.trim() !== "" && draft.address.trim() !== "" && draft.method.trim() !== "";
  const set = <K extends keyof NewConfirmationDraft>(
    key: K,
    value: NewConfirmationDraft[K],
  ): void => {
    setDraft((d) => ({ ...d, [key]: value }));
  };
  const field =
    "h-[34px] rounded-input bg-card px-[8px] text-cell inset-ring-[0.5px] inset-ring-stroke";
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={C.newTitle}
      {...(held === true ? { forceState: "open" as const, heldRole: "group" as const } : {})}
      action={
        <Button
          variant="primary"
          disabled={!complete || !independent}
          aria-describedby={independent ? undefined : ids.help}
          onClick={() => onSend?.(draft)}
        >
          {C.send}
        </Button>
      }
    >
      <div data-fieldwork="new-confirmation" className="flex flex-col gap-[10px] p-[16px]">
        <Label htmlFor={ids.type}>{C.type}</Label>
        <span id={ids.type}>
          <Picker
            label={C.type}
            options={Object.entries(C.types).map(([value, label]) => ({ value, label }))}
            value={draft.type}
            onChange={(value) => {
              set("type", value as NewConfirmationDraft["type"]);
            }}
          />
        </span>
        <Label htmlFor={ids.org}>{C.organisation}</Label>
        <input
          id={ids.org}
          className={field}
          value={draft.respondentOrg}
          onChange={(e) => {
            set("respondentOrg", e.target.value);
          }}
        />
        <Label htmlFor={ids.name}>{C.respondent}</Label>
        <input
          id={ids.name}
          className={field}
          value={draft.respondentName}
          onChange={(e) => {
            set("respondentName", e.target.value);
          }}
        />
        <Label htmlFor={ids.address}>{C.address}</Label>
        <input
          id={ids.address}
          className={field}
          value={draft.address}
          onChange={(e) => {
            set("address", e.target.value);
          }}
        />
        <Label htmlFor={ids.method}>{C.verification}</Label>
        <input
          id={ids.method}
          className={field}
          value={draft.method}
          onChange={(e) => {
            set("method", e.target.value);
          }}
        />
        <fieldset className="flex flex-wrap gap-[10px]">
          <legend className="mb-[6px] text-cell text-ink-2">{C.sources}</legend>
          {(Object.keys(C.sourceNames) as AddressSource[]).map((s) => (
            <label key={s} className="flex items-center gap-[6px] text-cell">
              <input
                type="checkbox"
                checked={draft.sources.includes(s)}
                onChange={(e) => {
                  set(
                    "sources",
                    e.target.checked
                      ? [...draft.sources, s]
                      : draft.sources.filter((x) => x !== s),
                  );
                }}
              />
              {C.sourceNames[s]}
            </label>
          ))}
        </fieldset>
        {!independent && (
          <p id={ids.help} data-fieldwork="send-helper" className="text-[11.5px] text-red-ink">
            {C.notVerified}
          </p>
        )}
      </div>
    </SheetModal>
  );
}
