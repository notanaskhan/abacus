import type { IntakeFieldOut, IntakeOut } from "@abacus/api-client";
import {
  intakeConfirmMutation,
  intakeCreateMutation,
  intakeOptions,
  intakeUpdateMutation,
  meOptions,
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
// 2848…) and Assign (Notify the signing partner) follow. A TIN is only ever its last four (the
// server sends no more). Creating the notice is the person's; the agent only read the letter.

const POLL_MS = 1_500;

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
  return (
    <div data-intake="extracted">
      {intake.fields
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

export function canCreate(intake: IntakeOut | undefined): boolean {
  return (
    intake !== undefined &&
    intake.status === "ready" &&
    !intake.fields.some((f) => f.low_confidence && !f.confirmed) &&
    intake.match.client_entity_id !== null
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
  const ready = canCreate(intake);
  const action = (
    <Button
      variant="primary"
      size="sm"
      disabled={!ready || confirm.isPending}
      onClick={() => {
        if (intake === undefined || intake.match.client_entity_id === null) return;
        confirm.mutate({
          path: { intake_id: intake.id },
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: {
            client_entity_id: intake.match.client_entity_id,
            assignee_id: intake.assignee_user_id ?? me?.user_id ?? "",
            notify_user_ids: notify ? (intake.notify_user_ids ?? []) : [],
          },
        });
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
                <Picker
                  label={COPY.intake.client}
                  className="flex-1"
                  {...(intake.match.client_entity_id === null
                    ? {}
                    : { defaultValue: intake.match.client_entity_id })}
                  options={intake.match.candidates.map((c) => ({
                    value: c.client_entity_id,
                    label: c.name,
                  }))}
                />
                {intake.match.method !== null && intake.match.method !== "manual" && (
                  <span className="text-micro text-green-ink">{COPY.intake.matched}</span>
                )}
              </div>
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
                  <Button variant="secondary" size="sm">
                    {COPY.intake.draft2848}
                  </Button>
                </div>
              )}
            </Card>
            <Card title={COPY.intake.assign}>
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
