import type { IntakeFieldOut, IntakeOut } from "@abacus/api-client";
import {
  firmMembersOptions,
  getClientOptions,
  intakeAttachMutation,
  intakeConfirmMutation,
  intakeCreateMutation,
  intakeOptions,
  intakeUpdateMutation,
  listClientsOptions,
  meOptions,
  noticeOptions,
} from "@abacus/api-client/query";
import {
  Button,
  ConfidencePill,
  Icon,
  Picker,
  SheetModal,
  Skeleton,
  StatusDisc,
  Toggle,
  cn,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useRef, useState } from "react";
import { COPY } from "./copy";

// NOT-01 b, c and d (N-04-T09; the handoff spec): the O3 intake sheet (500). Without an intake it
// is the DropZone, with a visible "Choose file…" button for the keyboard. With one it reads the
// intake (polled while the agent reads it): Source, then "Extracted by Accrued Agent" with every
// field editable and its ConfidencePill (green at 95% and above, amber below, the percent in
// text); a low-confidence field shows its helper and a Confirm, and Create notice stays disabled
// while the agent is reading or any low-confidence field is unconfirmed (409
// `low_confidence_unconfirmed` server-side). Match (client picker), Authorization (Draft Form
// 2848…) and Assign (assignee, Notify the signing partner) follow. A TIN is only ever its last four
// (the server sends no more). Creating the notice is the person's; the agent only read the letter.
// Composed (DEC-2329): Possible duplicate (Attach or Create anyway), Manual entry (the reason in
// words, empty fields, no pills) and No client matched (the picker). Corrections save at Create.

const POLL_MS = 1_500;

// What a person enters by hand, in the letter's order (no TIN: picking the client sets it).
const MANUAL_KEYS: readonly IntakeFieldOut["key"][] = [
  "agency.name",
  "notice.code",
  "notice.tax_year",
  "notice.form",
  "notice.date",
  "notice.respond_by",
  "notice.amount_total",
];

const LABEL: Readonly<Partial<Record<IntakeFieldOut["key"], string>>> = {
  "agency.name": "Agency",
  "notice.code": "Notice",
  "notice.tax_year": "Tax year",
  "notice.form": "Form",
  "notice.date": "Notice date",
  "notice.respond_by": "Respond by",
  "notice.amount_total": "Amount due",
  "taxpayer.name": "Taxpayer",
};

function Card({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="rounded-card bg-card shadow-e1">
      <h3 className="px-[14px] pt-[10px] pb-[6px] text-body font-medium">{title}</h3>
      {children}
    </section>
  );
}

function tinText(f: IntakeFieldOut | undefined): string | null {
  const last4 = f?.tin?.last4;
  return last4 == null ? null : `•••-••-${last4}`;
}

function FieldRow({
  field,
  tin,
  value,
  onValue,
  onConfirm,
}: {
  field: IntakeFieldOut;
  tin: string | null;
  value: string;
  onValue: (v: string) => void;
  onConfirm: () => void;
}): JSX.Element {
  const label = LABEL[field.key] ?? field.key;
  const unconfirmed = field.low_confidence && !field.confirmed;
  return (
    <div data-intake-field={field.key} className="hairline-t px-[14px] py-[6px]">
      <div className="flex min-h-[34px] items-center gap-[8px]">
        <span className="w-[110px] flex-none text-dense text-ink-2">{label}</span>
        <input
          aria-label={label}
          value={value}
          onChange={(e) => {
            onValue(e.target.value);
          }}
          className="min-w-0 flex-1 rounded-field bg-transparent px-[6px] py-[2px] text-body hover:bg-nested focus:bg-nested"
        />
        {tin !== null && <span className="text-body text-ink-2 tabular-nums">{tin}</span>}
        {field.confidence !== null && (
          <ConfidencePill
            value={field.confidence}
            {...(field.low_confidence && field.note != null ? { note: field.note } : {})}
          />
        )}
      </div>
      {unconfirmed && (
        <div className="flex items-center gap-[8px] pl-[118px] text-micro text-amber-ink">
          <span className="flex-1">{field.helper ?? COPY.intake.checkLetter}</span>
          <Button variant="secondary" size="sm" onClick={onConfirm}>
            {COPY.intake.confirm}
          </Button>
        </div>
      )}
    </div>
  );
}

function Extracted({
  intake,
  edits,
  onEdit,
  onConfirm,
}: {
  intake: IntakeOut;
  edits: Readonly<Record<string, string>>;
  onEdit: (key: string, value: string) => void;
  onConfirm: (field: IntakeFieldOut) => void;
}): JSX.Element {
  if (intake.status === "extracting") {
    return (
      <div data-intake="extracting" aria-busy="true" className="px-[14px] pb-[12px]">
        <p className="flex items-center gap-[8px] text-dense text-ink-2">
          <StatusDisc state="run" />
          {COPY.intake.reading(intake.pages ?? 1)}
        </p>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="mt-[8px] h-[26px] w-full" />
        ))}
      </div>
    );
  }
  const tin = tinText(intake.fields.find((f) => f.key === "taxpayer.tin"));
  const entering = intake.status === "manual_entry" || intake.status === "failed";
  const known = new Set(intake.fields.map((f) => f.key));
  const blank: IntakeFieldOut[] = entering
    ? MANUAL_KEYS.filter((key) => !known.has(key)).map((key) => ({
        key,
        value_text: null,
        confidence: null,
        low_confidence: false,
        confirmed: false,
        origin: "human",
      }))
    : [];
  return (
    <div data-intake={entering ? "manual" : "extracted"}>
      {entering && (
        <p data-intake="manual-reason" className="px-[14px] pb-[8px] text-dense text-ink-2">
          {intake.manual_reason ?? COPY.intake.manual}
        </p>
      )}
      {[...intake.fields, ...blank]
        .filter((f) => f.key !== "taxpayer.tin")
        .map((f) => (
          <FieldRow
            key={f.key}
            field={f}
            tin={f.key === "taxpayer.name" ? tin : null}
            value={edits[f.key] ?? f.value_text ?? ""}
            onValue={(v) => {
              onEdit(f.key, v);
            }}
            onConfirm={() => {
              onConfirm(f);
            }}
          />
        ))}
    </div>
  );
}

/** Create notice's own preconditions; a possible duplicate takes the banner's Create anyway. */
export function canCreate(intake: IntakeOut | undefined): boolean {
  return (
    intake !== undefined &&
    (intake.status === "ready" || intake.status === "manual_entry" || intake.status === "failed") &&
    !intake.fields.some((f) => f.low_confidence && !f.confirmed) &&
    intake.match.client_entity_id !== null &&
    intake.duplicate_of == null
  );
}

function DuplicateBanner({
  noticeId,
  disabled,
  onAttach,
  onCreateAnyway,
}: {
  noticeId: string;
  disabled: boolean;
  onAttach: () => void;
  onCreateAnyway: () => void;
}): JSX.Element {
  const code = useQuery(noticeOptions({ path: { notice_id: noticeId } })).data?.row.notice_code;
  return (
    <div
      data-intake="duplicate"
      className="flex flex-wrap items-center gap-[8px] rounded-nested bg-amber-tint px-[12px] py-[8px] text-dense"
    >
      <span className="min-w-0 flex-1">
        {code === undefined ? COPY.intake.duplicateFallback : COPY.intake.duplicate(code)}
      </span>
      <Button variant="secondary" size="sm" disabled={disabled} onClick={onAttach}>
        {code === undefined ? COPY.intake.attachFallback : COPY.intake.attach(code)}
      </Button>
      <Button variant="secondary" size="sm" disabled={disabled} onClick={onCreateAnyway}>
        {COPY.intake.createAnyway}
      </Button>
    </div>
  );
}

/** Code's candidates, or the firm's clients to choose from (then the client's entity). */
function ClientPicker({
  intake,
  onEntity,
}: {
  intake: IntakeOut;
  onEntity: (entity: string) => void;
}): JSX.Element {
  const [clientId, setClientId] = useState<string | null>(null);
  const match = intake.match;
  const picking = match.client_entity_id === null && match.candidates.length === 0;
  const clients = useQuery({
    ...listClientsOptions({ query: { limit: 100 } }),
    enabled: picking,
  }).data;
  const client = useQuery({
    ...getClientOptions({ path: { client_id: clientId ?? "" } }),
    enabled: clientId !== null,
  }).data;
  const entities = clientId === null ? [] : (client?.entities ?? []);
  const known =
    match.client_entity_id !== null && match.client_name !== null
      ? [{ value: match.client_entity_id, label: match.client_name }]
      : [];
  const options = picking
    ? (clients?.items ?? []).map((c) => ({ value: c.id, label: c.name }))
    : [...known, ...match.candidates.map((c) => ({ value: c.client_entity_id, label: c.name }))];
  return (
    <>
      <Picker
        key={match.client_entity_id ?? "none"}
        label={COPY.intake.client}
        className="flex-1"
        placeholder={COPY.intake.pickClient}
        {...(match.client_entity_id === null ? {} : { defaultValue: match.client_entity_id })}
        options={options}
        onChange={(picked) => {
          if (picking) setClientId(picked);
          else onEntity(picked);
        }}
      />
      {entities.length > 0 && (
        <Picker
          label={COPY.intake.entity}
          className="flex-1"
          placeholder={COPY.intake.pickEntity}
          options={entities.map((e) => ({ value: e.id, label: e.name }))}
          onChange={onEntity}
        />
      )}
    </>
  );
}

export function IntakeSheet({
  intakeId: initial,
  open,
  onOpenChange,
}: {
  intakeId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const me = useQuery(meOptions()).data;
  const [intakeId, setIntakeId] = useState(initial);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [notify, setNotify] = useState(true);
  const [assignee, setAssignee] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const read = useQuery({
    ...intakeOptions({ path: { intake_id: intakeId ?? "" } }),
    enabled: intakeId !== null,
    refetchInterval: (q) => (q.state.data?.status === "extracting" ? POLL_MS : false),
  });
  const intake = read.data;
  const refresh = (): void => {
    void read.refetch();
  };
  const start = useMutation({
    ...intakeCreateMutation(),
    onSuccess: (out) => {
      setIntakeId(out.id);
    },
  });
  const update = useMutation({ ...intakeUpdateMutation(), onSuccess: refresh });
  const members = useQuery({ ...firmMembersOptions(), enabled: open }).data;
  const confirm = useMutation({
    ...intakeConfirmMutation(),
    onSuccess: () => {
      toast.show({ kind: "success", text: COPY.intake.created });
      void queryClient.invalidateQueries({ queryKey: [{ _id: "notices" }] });
      onOpenChange(false);
    },
    onError: () => {
      toast.show({ kind: "error", text: COPY.intake.failed });
    },
  });
  const attach = useMutation({
    ...intakeAttachMutation(),
    onSuccess: () => {
      toast.show({ kind: "success", text: COPY.intake.attached });
      void queryClient.invalidateQueries({ queryKey: [{ _id: "notices" }] });
      onOpenChange(false);
    },
    onError: () => {
      toast.show({ kind: "error", text: COPY.intake.failed });
    },
  });
  const ready = canCreate(intake);
  const assigneeId = assignee ?? intake?.assignee_user_id ?? me?.user_id ?? "";
  /** A person's corrections are saved first, so Create notice adopts what they typed. */
  const createNotice = async (createAnyway: boolean): Promise<void> => {
    if (intake === undefined || intake.match.client_entity_id === null) return;
    const typed = Object.entries(edits);
    try {
      if (typed.length > 0) {
        await update.mutateAsync({
          path: { intake_id: intake.id },
          headers: { "If-Match": intake.version },
          body: {
            fields: typed.map(([key, value_text]) => ({
              key: key as Exclude<IntakeFieldOut["key"], "taxpayer.tin">,
              value_text,
            })),
          },
        });
        setEdits({});
      }
    } catch {
      toast.show({ kind: "error", text: COPY.intake.failed });
      return;
    }
    confirm.mutate({
      path: { intake_id: intake.id },
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: {
        client_entity_id: intake.match.client_entity_id,
        assignee_id: assigneeId,
        notify_user_ids: notify ? (intake.notify_user_ids ?? []) : [],
        create_anyway: createAnyway,
      },
    });
  };
  const action = (
    <Button
      variant="primary"
      size="sm"
      disabled={!ready || confirm.isPending || update.isPending}
      onClick={() => {
        void createNotice(false);
      }}
    >
      {COPY.intake.create}
    </Button>
  );
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.intake.title}
      action={action}
      dirty={Object.keys(edits).length > 0}
    >
      <div data-screen="NOT-01-intake" className="flex flex-col gap-[10px] p-[12px]">
        {intakeId === null ? (
          <div
            data-intake="drop"
            className="flex flex-col items-center gap-[10px] rounded-pane bg-nested p-[24px] text-center"
          >
            <Icon name="upload" size={18} className="text-ink-3" />
            <p className="text-dense text-ink-2">{COPY.intake.drop}</p>
            <input
              ref={fileInput}
              type="file"
              accept="application/pdf,image/jpeg,image/png,image/tiff"
              className="sr-only"
              aria-label={COPY.intake.choose}
              onChange={() => {
                start.mutate({
                  body: { source: "upload" },
                  headers: { "Idempotency-Key": crypto.randomUUID() },
                });
              }}
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                fileInput.current?.click();
              }}
            >
              {COPY.intake.choose}
            </Button>
          </div>
        ) : intake === undefined ? (
          <Skeleton className="h-[120px] w-full" />
        ) : (
          <>
            {intake.duplicate_of != null && (
              <DuplicateBanner
                noticeId={intake.duplicate_of}
                disabled={attach.isPending || confirm.isPending}
                onAttach={() => {
                  if (intake.duplicate_of == null) return;
                  attach.mutate({
                    path: { intake_id: intake.id },
                    headers: { "Idempotency-Key": crypto.randomUUID() },
                    body: { notice_id: intake.duplicate_of },
                  });
                }}
                onCreateAnyway={() => {
                  void createNotice(true);
                }}
              />
            )}
            <Card title={COPY.intake.source}>
              <p className="px-[14px] pb-[10px] text-dense">
                {intake.file_name}
                {intake.pages !== null && ` · ${COPY.intake.pages(intake.pages)}`}
                {intake.uploaded_by_label !== null && (
                  <span className="block text-micro text-ink-3">{intake.uploaded_by_label}</span>
                )}
              </p>
            </Card>
            <Card title={COPY.intake.extracted}>
              <Extracted
                intake={intake}
                edits={edits}
                onEdit={(key, value) => {
                  setEdits((e) => ({ ...e, [key]: value }));
                }}
                onConfirm={(f) => {
                  update.mutate({
                    path: { intake_id: intake.id },
                    headers: { "If-Match": intake.version },
                    body: {
                      fields: [
                        {
                          key: f.key as Exclude<IntakeFieldOut["key"], "taxpayer.tin">,
                          confirm: true,
                          value_text: edits[f.key] ?? f.value_text,
                        },
                      ],
                    },
                  });
                }}
              />
            </Card>
            <Card title={COPY.intake.match}>
              <div className="flex min-h-[34px] items-center gap-[8px] px-[14px] pb-[8px] text-dense">
                <span className="w-[110px] text-ink-2">{COPY.intake.client}</span>
                <ClientPicker
                  intake={intake}
                  onEntity={(entity) => {
                    update.mutate({
                      path: { intake_id: intake.id },
                      headers: { "If-Match": intake.version },
                      body: { client_entity_id: entity },
                    });
                  }}
                />
                {intake.match.method !== null && intake.match.method !== "manual" && (
                  <span className="text-micro text-green-ink">{COPY.intake.matched}</span>
                )}
              </div>
              {intake.match.client_entity_id === null && (
                <p
                  data-intake="no-client"
                  className="px-[14px] pb-[8px] text-micro text-amber-ink"
                >
                  {COPY.intake.noClient}
                </p>
              )}
              {intake.match.return_label !== null && (
                <p className="hairline-t px-[14px] py-[8px] text-dense">
                  {intake.match.return_label}
                </p>
              )}
            </Card>
            <Card title={COPY.intake.authorization}>
              {intake.authorization.on_file ? (
                <p className="px-[14px] pb-[10px] text-dense">{intake.authorization.label}</p>
              ) : (
                <div className="mx-[14px] mb-[10px] flex items-center gap-[8px] rounded-nested bg-red-tint px-[10px] py-[8px] text-dense text-red-ink">
                  <span className="flex-1">{intake.authorization.label}</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled
                    title={COPY.intake.draft2848Waiting}
                  >
                    {COPY.intake.draft2848}
                  </Button>
                </div>
              )}
            </Card>
            <Card title={COPY.intake.assign}>
              <div className="flex min-h-[34px] items-center gap-[8px] px-[14px] text-dense">
                <span className="w-[110px] text-ink-2">{COPY.intake.assignee}</span>
                <Picker
                  key={assigneeId}
                  label={COPY.intake.assignee}
                  className="flex-1"
                  {...(assigneeId === "" ? {} : { defaultValue: assigneeId })}
                  options={(members ?? []).map((m) => ({
                    value: m.user_id,
                    label: m.display_name,
                  }))}
                  onChange={setAssignee}
                />
              </div>
              <div
                className={cn(
                  "flex min-h-[34px] items-center gap-[8px] px-[14px] pb-[8px] text-dense",
                )}
              >
                <span className="flex-1 text-ink-2">{COPY.intake.notify}</span>
                <Toggle label={COPY.intake.notify} checked={notify} onChange={setNotify} />
              </div>
            </Card>
          </>
        )}
      </div>
    </SheetModal>
  );
}
