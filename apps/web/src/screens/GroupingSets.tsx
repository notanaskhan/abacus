import type { GroupingVersionOut } from "@abacus/api-client";
import {
  groupingSetVersionsOptions,
  groupingSetVersionsQueryKey,
  importGroupingSetMutation,
  publishGroupingSetMutation,
} from "@abacus/api-client/query";
import { Alert, Button, EmptyState, Fieldset, Skeleton, StatusPill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-316 (TASK-345): the firm's FS groupings (its taxonomy) are content, loaded here from CSV
// into a draft with any problems listed by row, then published once by a quality partner or
// practice leader. Engagements map their trial balances with a published version.

export const COLUMNS =
  "grouping_key, grouping_label, class, fs_line_key, fs_line_label, normal_balance, account_from, account_to";

const PROBLEM: Record<string, string> = {
  header: "The first row must name the columns",
  missing_key: "A grouping key and an FS line key are needed",
  class_invalid: "Class must be assets, liabilities, equity, revenue or expenses",
  normal_balance_invalid: "Normal balance must be debit or credit",
  duplicate_key: "A key is used with a different label or parent",
  range_invalid: "The range runs backwards",
  overlapping_range: "Account ranges overlap",
  too_many_rows: "Too many rows",
};

export function problemWord(p: GroupingVersionOut["problems"][number]): string {
  const where = p.row > 0 ? `Row ${String(p.row)}: ` : "";
  return `${where}${PROBLEM[p.code] ?? p.code} (${p.detail})`;
}

export function GroupingSets(): JSX.Element {
  const queryClient = useQueryClient();
  const list = useQuery({ ...groupingSetVersionsOptions(), retry: false });
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [csv, setCsv] = useState("");
  const store = (data: GroupingVersionOut[]): void => {
    queryClient.setQueryData(groupingSetVersionsQueryKey(), data);
  };
  const fail = (e: unknown): void => {
    const code = errorMessage(e);
    toast.show(
      code === "grouping_set_has_problems"
        ? "Fix the problems and import again before publishing."
        : code === "forbidden"
          ? "Your role can't do that (publishing needs a recent sign-in check)."
          : code,
    );
  };
  const importSet = useMutation({
    ...importGroupingSetMutation(),
    onSuccess: (data) => {
      store(data);
      setCsv("");
    },
    onError: fail,
  });
  const publish = useMutation({
    ...publishGroupingSetMutation(),
    onSuccess: store,
    onError: fail,
  });
  if (list.isPending) return <Skeleton className="h-64" />;
  if (list.isError) {
    return (
      <Alert title="FS groupings aren't available">
        {errorMessage(list.error) === "forbidden"
          ? "FS groupings are managed by the firm's admins, practice leaders and quality partners."
          : errorMessage(list.error)}
      </Alert>
    );
  }
  const input = "h-[30px] rounded-tile border-0 bg-nested px-2.5 inset-shadow-hair";
  return (
    <div className="flex flex-col gap-3">
      <section className="rounded-pane bg-card shadow-e2">
        <div className="flex min-h-[50px] items-center border-b-[0.5px] border-hair px-4">
          <h2 className="text-[15px] font-medium tracking-[-0.012em]">FS groupings</h2>
        </div>
        {list.data.length === 0 ? (
          <EmptyState title="No FS groupings yet">
            Import your firm's groupings, FS lines and account ranges below.
          </EmptyState>
        ) : (
          <ul className="flex flex-col">
            {list.data.map((v) => (
              <li
                key={v.id}
                className="flex flex-col gap-1 border-t-[0.5px] border-hair px-4 py-2.5 first:border-t-0"
              >
                <div className="flex items-center gap-2 text-[13px]">
                  <span className="font-medium">{v.set_name}</span>
                  <span className="text-ink-3 tabular-nums">{`v${String(v.version)}`}</span>
                  {v.status === "published" ? (
                    <StatusPill tone="success">Published</StatusPill>
                  ) : v.problems.length > 0 ? (
                    <StatusPill tone="warning">{`Draft · ${String(v.problems.length)} problems`}</StatusPill>
                  ) : (
                    <StatusPill tone="neutral">Draft</StatusPill>
                  )}
                  <span className="flex-1" />
                  {v.status === "draft" && v.problems.length === 0 && (
                    <Button
                      size="sm"
                      disabled={publish.isPending}
                      onClick={() => {
                        publish.mutate({ path: { version_id: v.id } });
                      }}
                    >
                      Publish
                    </Button>
                  )}
                </div>
                {v.problems.length > 0 && (
                  <ul
                    aria-label={`Problems in ${v.set_name} v${String(v.version)}`}
                    className="text-[12.5px] text-ink-2"
                  >
                    {v.problems.slice(0, 20).map((p, i) => (
                      <li key={i}>{problemWord(p)}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="rounded-pane bg-card p-4 shadow-e2">
        <h3 className="mb-2 text-[13px] font-medium">Import</h3>
        <Fieldset>
          <div className="flex flex-col gap-2 text-[13px]">
            <div className="flex flex-wrap gap-2">
              <input
                aria-label="Key"
                placeholder="bh-fs"
                value={key}
                maxLength={40}
                onChange={(e) => {
                  setKey(e.target.value);
                }}
                className={`${input} w-[160px]`}
              />
              <input
                aria-label="Name"
                placeholder="BH FS groupings"
                value={name}
                maxLength={120}
                onChange={(e) => {
                  setName(e.target.value);
                }}
                className={`${input} flex-1`}
              />
              <label className="inline-flex cursor-pointer items-center rounded-tile px-2 text-accent hover:underline">
                Choose a CSV file…
                <input
                  type="file"
                  accept=".csv,text/csv"
                  className="sr-only"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file !== undefined) void file.text().then(setCsv);
                  }}
                />
              </label>
            </div>
            <textarea
              aria-label="CSV"
              value={csv}
              placeholder={COLUMNS}
              onChange={(e) => {
                setCsv(e.target.value);
              }}
              className="h-[160px] w-full rounded-tile border-0 bg-nested p-2.5 font-mono text-[12px] inset-shadow-hair"
            />
            <p className="text-[12px] text-ink-3">{`Columns: ${COLUMNS}. One row per FS line, or per extra account range of a line.`}</p>
            <div>
              <Button
                disabled={
                  !/^[a-z0-9][a-z0-9_-]{0,39}$/.test(key.trim().toLowerCase()) ||
                  name.trim() === "" ||
                  csv.trim() === "" ||
                  importSet.isPending
                }
                onClick={() => {
                  importSet.mutate({
                    body: { key: key.trim().toLowerCase(), name: name.trim(), csv },
                  });
                }}
              >
                Import as a draft
              </Button>
            </div>
          </div>
        </Fieldset>
      </section>
    </div>
  );
}
