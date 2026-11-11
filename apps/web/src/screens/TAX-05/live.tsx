// T-04-T29 (TASK-6828): TAX-05 Worksheets and TXI-01's editor on a live build. The return's
// worksheets (`GET /v1/tax/returns/{id}/worksheets`), one worksheet's sections and fields
// (`GET /v1/tax/worksheets/{id}/fields`), an edit with a required reason (P-04's
// `PUT /v1/fields/return_worksheet/{id}/{key}/value` with the version the person saw; the reason is
// the edit's note) and a section's sign-off through SHL-12 (`?ov=signoff:return_worksheet_section:
// <id>`; the sheet writes and waits for the server). Engine lines are read-only. A refusal shows
// its words.
import {
  fieldEditMutation,
  worksheetFieldsOptions,
  worksheetsOptions,
} from "@abacus/api-client/query";
import type { WorksheetFieldOut, WorksheetNodeOut } from "@abacus/api-client";
import { Button, EmptyState, Pill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { ov } from "../../routes/to";
import { blockerWords, RETURN_LIVE_KEYS, useReturnLive } from "../TAX-04/live-core";

export const WORKSHEETS_LIVE_COPY = {
  loading: "Loading worksheets…",
  empty: "No worksheets on this return yet.",
  pick: "Pick a worksheet",
  edit: "Edit",
  save: "Save",
  cancel: "Cancel",
  reason: "Reason for the change",
  reasonRequired: "A reason is required.",
  signOff: "Sign off…",
  signedOff: "Signed off",
  engine: "From the engine",
  edited: "Edited",
} as const;

export interface WorksheetsLiveProps {
  returnId: string;
  engagementId: string | undefined;
  /** TXI-01 opens straight on one worksheet. */
  worksheetId?: string;
}

function FieldRow({
  worksheetId,
  field,
  onRefresh,
}: {
  worksheetId: string;
  field: WorksheetFieldOut;
  onRefresh: () => void;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(field.value ?? "");
  const [reason, setReason] = useState("");
  const [words, setWords] = useState<string[]>([]);
  const edit = useMutation({ ...fieldEditMutation(), onSettled: onRefresh });
  const engine = field.engine_label != null;
  const save = async (): Promise<void> => {
    if (reason.trim() === "") {
      setWords([WORKSHEETS_LIVE_COPY.reasonRequired]);
      return;
    }
    setWords([]);
    try {
      await edit.mutateAsync({
        path: {
          target_type: "return_worksheet",
          target_id: worksheetId,
          field_key: field.field_key,
        },
        body: {
          value: { t: "decimal", v: value.trim() === "" ? null : value.trim() },
          seen_seq: field.seen_seq,
          citation_note: reason.trim(),
        },
      });
      setEditing(false);
      setReason("");
    } catch (error) {
      setWords(blockerWords(error));
    }
  };
  return (
    <li
      data-field={field.field_key}
      data-state={field.state}
      className="flex flex-col gap-[4px] border-b border-hairline px-[12px] py-[6px]"
    >
      <div className="flex min-h-[30px] items-center gap-[8px]">
        <span className="min-w-0 flex-1 truncate text-[13px]">{field.label}</span>
        {engine ? (
          <Pill variant="muted" size="state">
            {field.engine_label ?? WORKSHEETS_LIVE_COPY.engine}
          </Pill>
        ) : null}
        {editing ? (
          <input
            aria-label={field.label}
            inputMode="decimal"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
            }}
            className="w-[110px] rounded-[6px] border border-hairline px-[6px] text-right text-[13px] tabular-nums"
          />
        ) : (
          <span className="w-[110px] text-right text-[13px] tabular-nums">
            {field.value ?? ""}
          </span>
        )}
        {engine ? null : editing ? null : (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setValue(field.value ?? "");
              setEditing(true);
            }}
          >
            {WORKSHEETS_LIVE_COPY.edit}
          </Button>
        )}
      </div>
      {editing ? (
        <div className="flex items-center gap-[6px]">
          <input
            aria-label={WORKSHEETS_LIVE_COPY.reason}
            placeholder={WORKSHEETS_LIVE_COPY.reason}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
            }}
            className="flex-1 rounded-[6px] border border-hairline px-[6px] text-[12.5px]"
          />
          <Button
            variant="primary"
            size="sm"
            disabled={edit.isPending}
            onClick={() => void save()}
          >
            {WORKSHEETS_LIVE_COPY.save}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setEditing(false);
              setWords([]);
            }}
          >
            {WORKSHEETS_LIVE_COPY.cancel}
          </Button>
        </div>
      ) : null}
      {words.map((w) => (
        <p key={w} role="alert" className="text-[12.5px] text-red-ink">
          {w}
        </p>
      ))}
    </li>
  );
}

function Fields({
  worksheetId,
  interval,
}: {
  worksheetId: string;
  interval: number | false;
}): JSX.Element {
  const queryClient = useQueryClient();
  const open = useOpenOverlay();
  const fields = useQuery({
    ...worksheetFieldsOptions({ path: { worksheet_id: worksheetId } }),
    refetchInterval: interval,
  });
  const refresh = (): void => {
    for (const queryKey of RETURN_LIVE_KEYS) void queryClient.invalidateQueries({ queryKey });
  };
  if (fields.isPending) {
    return <p className="p-[12px] text-ink-3">{WORKSHEETS_LIVE_COPY.loading}</p>;
  }
  return (
    <div data-worksheet={worksheetId} className="flex flex-col gap-[10px]">
      {(fields.data?.sections ?? []).map((section) => (
        <section key={section.key} aria-label={section.title} data-section={section.key}>
          <div className="flex h-[31px] items-center gap-[8px] bg-band-hd px-[12px]">
            <span className="flex-1 text-[13.5px] font-medium">{section.title}</span>
            {section.signed_off === true ? (
              <Pill variant="green-tint" size="state">
                {WORKSHEETS_LIVE_COPY.signedOff}
              </Pill>
            ) : null}
            {section.section_id != null ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  open(ov.SHL12("return_worksheet_section", section.section_id as string));
                }}
              >
                {WORKSHEETS_LIVE_COPY.signOff}
              </Button>
            ) : null}
          </div>
          <ul className="flex flex-col">
            {section.fields.map((f) => (
              <FieldRow
                key={f.field_key}
                worksheetId={worksheetId}
                field={f}
                onRefresh={refresh}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export function WorksheetsLive({
  returnId,
  engagementId,
  worksheetId,
}: WorksheetsLiveProps): JSX.Element {
  const interval = useReturnLive(engagementId);
  const sheets = useQuery({
    ...worksheetsOptions({ path: { return_id: returnId } }),
    refetchInterval: interval,
  });
  const [picked, setPicked] = useState<string | undefined>(worksheetId);
  if (sheets.isPending) {
    return (
      <div data-screen="TAX-05" data-live aria-busy="true" className="p-[16px] text-ink-3">
        {WORKSHEETS_LIVE_COPY.loading}
      </div>
    );
  }
  const items: readonly WorksheetNodeOut[] = sheets.data?.items ?? [];
  if (items.length === 0) {
    return (
      <div data-screen="TAX-05" data-live>
        <EmptyState title={WORKSHEETS_LIVE_COPY.empty} />
      </div>
    );
  }
  const current = picked ?? items[0]?.worksheet_id;
  return (
    <div
      data-screen={worksheetId === undefined ? "TAX-05" : "TXI-01"}
      data-live
      className="flex gap-[10px] p-[12px]"
    >
      {worksheetId === undefined ? (
        <nav aria-label="Worksheets" className="flex w-[262px] shrink-0 flex-col">
          {[...new Set(items.map((w) => w.group))].map((group) => (
            <div key={group} className="flex flex-col">
              <div className="px-[8px] py-[4px] text-[12.5px] text-ink-2">{group}</div>
              {items
                .filter((w) => w.group === group)
                .map((w) => (
                  <button
                    key={w.worksheet_id}
                    type="button"
                    aria-current={w.worksheet_id === current ? "page" : undefined}
                    onClick={() => {
                      setPicked(w.worksheet_id);
                    }}
                    className={`flex items-center gap-[6px] rounded-[6px] px-[8px] py-[6px] text-left text-[13px] ${w.worksheet_id === current ? "bg-nested font-medium" : ""}`}
                  >
                    <span className="min-w-0 flex-1 truncate">{w.title}</span>
                    {w.edited === true ? (
                      <Pill variant="amber" size="state">
                        {WORKSHEETS_LIVE_COPY.edited}
                      </Pill>
                    ) : null}
                  </button>
                ))}
            </div>
          ))}
        </nav>
      ) : null}
      <div className="min-w-0 flex-1 rounded-pane bg-card shadow-e1">
        {current === undefined ? (
          <EmptyState title={WORKSHEETS_LIVE_COPY.pick} />
        ) : (
          <Fields key={current} worksheetId={current} interval={interval} />
        )}
      </div>
    </div>
  );
}
