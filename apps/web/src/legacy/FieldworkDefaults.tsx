import type { CriteriaIoInput as CriteriaIo } from "@abacus/api-client";
import {
  fieldworkSettingsOptions,
  fieldworkSettingsQueryKey,
  setFieldworkSettingsMutation,
} from "@abacus/api-client/query";
import { Alert, Button, Label, Panel, Skeleton } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

// SPEC-037 Q6 (TASK-084): the firm's default criteria for journal entry testing, copied into
// each new procedure. Changing them is `methodology.manage` (fresh MFA).

export function FieldworkDefaults({ canSet }: { canSet: boolean }): JSX.Element {
  const queryClient = useQueryClient();
  const current = useQuery({ ...fieldworkSettingsOptions(), retry: false });
  const [form, setForm] = useState<CriteriaIo | null>(null);
  const [confirm, setConfirm] = useState(false);
  const save = useMutation({
    ...setFieldworkSettingsMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(fieldworkSettingsQueryKey(), data);
      setForm(null);
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  if (current.isPending) return <Skeleton className="h-32" />;
  if (current.isError) {
    if (isForbidden(current.error)) return <></>;
    return <Alert title="Couldn't load the defaults">{errorMessage(current.error)}</Alert>;
  }
  const shown = form ?? current.data;
  const number = (key: keyof CriteriaIo, label: string): JSX.Element => (
    <div className="flex flex-col gap-1">
      <Label htmlFor={`jet-${key}`}>{label}</Label>
      <input
        id={`jet-${key}`}
        inputMode="numeric"
        disabled={!canSet}
        value={String(shown[key] ?? "")}
        onChange={(e) => {
          setForm({ ...shown, [key]: e.target.value });
        }}
        className="rounded-[var(--radius-control)] border border-hair bg-surface p-2 text-body"
      />
    </div>
  );
  return (
    <Panel title="Journal entry testing defaults">
      <div className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-3">
          {number("threshold_percent", "Threshold (% of performance materiality)")}
          {number("round_unit", "Round amount unit")}
          {number("window_days", "Days before year end")}
          {number("rare_count", "Rare account: fewer postings than")}
          {number("random_count", "Random entries")}
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="jet-keywords">Flagged words (comma separated)</Label>
          <input
            id="jet-keywords"
            disabled={!canSet}
            value={(shown.keywords ?? []).join(", ")}
            onChange={(e) => {
              setForm({
                ...shown,
                keywords: e.target.value
                  .split(",")
                  .map((w) => w.trim())
                  .filter((w) => w !== ""),
              });
            }}
            className="rounded-[var(--radius-control)] border border-hair bg-surface p-2 text-body"
          />
        </div>
        {canSet && (
          <div>
            <Button
              size="sm"
              disabled={form === null || save.isPending}
              onClick={() => {
                if (form !== null) {
                  save.mutate({
                    body: {
                      ...form,
                      threshold_percent: Number(form.threshold_percent),
                      window_days: Number(form.window_days),
                      rare_count: Number(form.rare_count),
                      random_count: Number(form.random_count),
                    },
                  });
                }
              }}
            >
              Save defaults
            </Button>
          </div>
        )}
        {save.isError && !confirm && (
          <Alert title="Couldn't save">Check the numbers and try again.</Alert>
        )}
      </div>
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}
