import {
  extensionOptions,
  extensionPatchMutation,
  extensionsOptions,
  listEvidenceVersionsOptions,
} from "@abacus/api-client/query";
import { Button, Dialog, Skeleton, ValueRow, date, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { COPY } from "./copy";

// TAX-13's Mark filed dialog (T-03-T16; `?ov=mark-filed:<extensionId>`): a person records that the
// firm transmitted this line. Nothing here files: Accrued never transmits. The line's own version
// goes in If-Match, so a second line on the return is never refused for the first one's edit. The
// service requires the filed form's evidence version (`filed_needs_evidence`), so the person names it
// from the engagement's uploaded versions.

const isoDay = (at: Date): string =>
  `${String(at.getFullYear())}-${String(at.getMonth() + 1).padStart(2, "0")}-${String(at.getDate()).padStart(2, "0")}`;

export interface MarkFiledDialogProps {
  taxYear: number;
  extensionId: string;
  onClose: () => void;
}

export function MarkFiledDialog({
  taxYear,
  extensionId,
  onClose,
}: MarkFiledDialogProps): JSX.Element {
  const now = useNow();
  const queries = useQueryClient();
  const found = useQuery(extensionOptions({ path: { extension_id: extensionId } }));
  const line = found.data?.lines.find((l) => l.extension_id === extensionId);
  const [filedOn, setFiledOn] = useState(() => isoDay(now));
  const [versionId, setVersionId] = useState<string | null>(null);
  const engagementId = found.data?.engagement_id ?? null;
  const versions = useQuery({
    ...listEvidenceVersionsOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== null,
  });
  const uploaded = (versions.data ?? []).filter((v) => v.method === "uploaded");
  const patch = useMutation(extensionPatchMutation());
  const form = line?.form ?? "";
  const save = (): void => {
    if (line === undefined || versionId === null) return;
    patch.mutate(
      {
        path: { extension_id: extensionId },
        body: { filed_on: filedOn, form, filed_form_evidence_version_id: versionId },
        headers: { "If-Match": line.row_version ?? found.data?.row_version ?? 1 },
      },
      {
        onSuccess: () => {
          toast.show(COPY.markFiled.done(form));
          void queries.invalidateQueries({
            queryKey: extensionsOptions({ query: { tax_year: taxYear } }).queryKey,
          });
          onClose();
        },
      },
    );
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.markFiled.title(form)}
      action={
        <Button
          variant="primary"
          disabled={line === undefined || filedOn === "" || versionId === null || patch.isPending}
          onClick={save}
        >
          {COPY.markFiled.action}
        </Button>
      }
    >
      {found.data === undefined ? (
        <Skeleton className="h-[60px]" />
      ) : (
        <div data-mark-filed className="flex flex-col gap-[10px]">
          <label className="flex items-center justify-between gap-[12px] text-[12.5px]">
            {COPY.markFiled.filedOn}
            <input
              type="date"
              className="h-[30px] rounded-full bg-card px-[12px] text-[13px] shadow-e1"
              max={isoDay(now)}
              value={filedOn}
              onChange={(event) => {
                setFiledOn(event.target.value);
              }}
            />
          </label>
          {versions.data !== undefined && uploaded.length === 0 ? (
            <p data-no-filed-form className="text-para text-ink-3">
              {COPY.markFiled.noForm}
            </p>
          ) : (
            <ValueRow
              kind="select"
              label={COPY.markFiled.form}
              placeholder={COPY.markFiled.choose}
              options={uploaded.map((v) => ({
                value: v.id,
                label: v.source,
                hint: date(v.created_at, { now }),
              }))}
              {...(versionId === null ? {} : { value: versionId })}
              onChange={setVersionId}
            />
          )}
          <p className="text-para text-ink-3">{COPY.markFiled.note}</p>
          {patch.isError && (
            <p role="alert" className="text-meta text-red-ink">
              {COPY.markFiled.failed}
            </p>
          )}
        </div>
      )}
    </Dialog>
  );
}
