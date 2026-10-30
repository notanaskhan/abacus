import type { FsStatementsOut, MappingOut } from "@abacus/api-client";
import {
  editMappingMutation,
  mappingOptions,
  mappingQueryKey,
  prepareMappingMutation,
  reviewMappingMutation,
  startMappingMutation,
  statementsOptions,
} from "@abacus/api-client/query";
import { Alert, Button, Skeleton, StatusPill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, type JSX, useState } from "react";
import { errorMessage } from "../api";
import { amount } from "./amounts";

// SPEC-316 (TASK-345): the trial balance mapped to the firm's FS lines (rules from account
// ranges, people's edits on top), and the draft statements code builds from it. Every amount,
// total and check comes from the server.

const EDITORS = new Set(["engagement_partner", "manager", "senior"]);
const PREPARERS = new Set(["manager", "senior", "staff"]);
const REVIEWERS = new Set(["engagement_partner", "manager", "senior"]);

type Path = { path: { engagement_id: string; tb_id: string } };

export function TbMapping({
  path,
  role,
  unit,
}: {
  path: Path;
  role: string;
  unit: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const mapping = useQuery({ ...mappingOptions(path), retry: false });
  const [version, setVersion] = useState("");
  const [onlyUnmapped, setOnlyUnmapped] = useState(false);
  const opts = {
    onSuccess: (data: MappingOut) => {
      queryClient.setQueryData(mappingQueryKey(path), data);
    },
    onError: (e: unknown) => {
      const code = errorMessage(e);
      toast.show(
        code === "unmapped_accounts"
          ? "Map every account before signing."
          : code === "preparer_cannot_review"
            ? "Someone other than the preparer reviews."
            : code === "not_prepared"
              ? "The preparer signs first."
              : code,
      );
    },
  };
  const startMap = useMutation({ ...startMappingMutation(), ...opts });
  const edit = useMutation({ ...editMappingMutation(), ...opts });
  const prepare = useMutation({ ...prepareMappingMutation(), ...opts });
  const review = useMutation({ ...reviewMappingMutation(), ...opts });
  if (mapping.isPending) return <Skeleton className="m-4 h-40" />;
  if (mapping.isError)
    return <Alert title="Mapping isn't available">{errorMessage(mapping.error)}</Alert>;
  const m = mapping.data;
  const canEdit = EDITORS.has(role);
  if (m.mapping_set_id == null) {
    return (
      <div className="flex flex-col gap-2 p-4 text-[13px]">
        {m.published_versions.length === 0 ? (
          <p className="text-ink-3">
            No published FS groupings yet. The firm imports and publishes them under Settings › FS
            groupings.
          </p>
        ) : (
          <>
            <p className="text-ink-2">Map this trial balance to the firm's FS lines.</p>
            <div className="flex items-center gap-2">
              <select
                aria-label="FS groupings"
                value={version}
                onChange={(e) => {
                  setVersion(e.target.value);
                }}
                className="h-[30px] rounded-tile border-0 bg-nested px-2 inset-shadow-hair"
              >
                <option value="">Choose FS groupings…</option>
                {m.published_versions.map((v) => (
                  <option key={v.id} value={v.id}>{`${v.set_name} v${String(v.version)}`}</option>
                ))}
              </select>
              <Button
                disabled={!canEdit || version === "" || startMap.isPending}
                onClick={() => {
                  startMap.mutate({ ...path, body: { grouping_set_version_id: version } });
                }}
              >
                Map with these groupings
              </Button>
            </div>
          </>
        )}
      </div>
    );
  }
  const shown = onlyUnmapped ? m.accounts.filter((a) => a.fs_line_id == null) : m.accounts;
  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b-[0.5px] border-hair px-4 py-2 text-[12.5px]">
        <span className="font-medium">{`${m.version?.set_name ?? ""} v${String(m.version?.version ?? "")}`}</span>
        <span className="text-ink-3 tabular-nums">{`${String(m.mapped)} mapped · ${String(m.prior_year ?? 0)} from prior year · ${String(m.number_range ?? 0)} by range · ${String(m.manual)} edited`}</span>
        {m.tb_balanced === false && (
          <StatusPill tone="danger">Trial balance out of balance</StatusPill>
        )}
        {m.unmapped > 0 ? (
          <StatusPill tone="warning">{`${String(m.unmapped)} unmapped`}</StatusPill>
        ) : (
          <StatusPill tone="success">All mapped</StatusPill>
        )}
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={onlyUnmapped}
            onChange={(e) => {
              setOnlyUnmapped(e.target.checked);
            }}
          />
          Unmapped only
        </label>
        <span className="flex-1" />
        {PREPARERS.has(role) && (
          <Button
            size="sm"
            variant="secondary"
            disabled={m.unmapped > 0 || prepare.isPending}
            onClick={() => {
              prepare.mutate({ ...path });
            }}
          >
            Sign as preparer
          </Button>
        )}
        {REVIEWERS.has(role) && (
          <Button
            size="sm"
            variant="secondary"
            disabled={m.unmapped > 0 || review.isPending}
            onClick={() => {
              review.mutate({ ...path });
            }}
          >
            Sign as reviewer
          </Button>
        )}
      </div>
      <div className="max-h-[600px] overflow-auto">
        <table className="w-full border-collapse text-[12.5px]">
          <thead className="sticky top-0 bg-band-hd text-ink-3">
            <tr>
              <th scope="col" className="px-2 py-1.5 text-left font-medium">
                Account
              </th>
              <th scope="col" className="px-2 py-1.5 text-right font-medium">
                End of year
              </th>
              <th scope="col" className="px-2 py-1.5 text-left font-medium">
                FS line
              </th>
              <th scope="col" className="px-2 py-1.5 text-left font-medium">
                How
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map((a) => (
              <tr key={a.account_code} className="border-t-[0.5px] border-hair">
                <td className="px-2 py-1">
                  <span className="mr-2 tabular-nums text-ink-3">{a.account_code}</span>
                  {a.account_name}
                </td>
                <td className="px-2 py-1 text-right tabular-nums">{amount(a.eoy, unit)}</td>
                <td className="px-2 py-1">
                  <select
                    aria-label={`FS line for ${a.account_code}`}
                    disabled={!canEdit || edit.isPending}
                    value={a.fs_line_id ?? ""}
                    onChange={(e) => {
                      edit.mutate({
                        ...path,
                        body: {
                          accounts: [
                            {
                              account_code: a.account_code,
                              ...(e.target.value === "" ? {} : { fs_line_id: e.target.value }),
                            },
                          ],
                        },
                      });
                    }}
                    className={`h-[26px] w-full max-w-[320px] rounded-tile border-0 px-1.5 inset-shadow-hair ${a.fs_line_id == null ? "bg-amber-tint" : "bg-nested"}`}
                  >
                    <option value="">
                      {a.fs_line_id == null ? "Unmapped" : "Back to the rules"}
                    </option>
                    {m.groupings.map((g) => (
                      <optgroup key={g.id} label={g.label}>
                        {g.lines.map((line) => (
                          <option key={line.id} value={line.id}>
                            {line.label}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-1 text-ink-3">
                  {a.method === "manual"
                    ? "Edited"
                    : a.method === "prior_year"
                      ? "Prior year"
                      : a.method === "number_range"
                        ? "Account range"
                        : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const CLASS_TITLE: Record<string, string> = {
  assets: "Total assets",
  liabilities: "Total liabilities",
  equity: "Total equity",
  revenue: "Total revenue",
  expenses: "Total expenses",
};

function Section({
  s,
  classes,
  unit,
}: {
  s: FsStatementsOut;
  classes: string[];
  unit: string;
}): JSX.Element {
  const hasPrior = s.py_totals != null;
  return (
    <>
      {classes.map((cls) => (
        <tbody key={cls}>
          {s.groups
            .filter((g) => g.class === cls)
            .map((g) => (
              <Fragment key={g.key}>
                <tr key={`${g.key}-h`}>
                  <th
                    scope="rowgroup"
                    colSpan={hasPrior ? 3 : 2}
                    className="px-3 pt-2 text-left font-medium"
                  >
                    {g.label}
                  </th>
                </tr>
                {g.lines.map((line) => (
                  <tr key={line.key}>
                    <td className="px-3 py-0.5 pl-6">{line.label}</td>
                    <td className="px-3 py-0.5 text-right tabular-nums">
                      {amount(line.cy, unit)}
                    </td>
                    {hasPrior && (
                      <td className="px-3 py-0.5 text-right tabular-nums text-ink-3">
                        {amount(line.py, unit)}
                      </td>
                    )}
                  </tr>
                ))}
              </Fragment>
            ))}
          <tr className="border-t-[0.5px] border-hair font-medium">
            <td className="px-3 py-1">{CLASS_TITLE[cls]}</td>
            <td className="px-3 py-1 text-right tabular-nums">{amount(s.totals[cls], unit)}</td>
            {hasPrior && (
              <td className="px-3 py-1 text-right tabular-nums text-ink-3">
                {amount(s.py_totals?.[cls], unit)}
              </td>
            )}
          </tr>
        </tbody>
      ))}
    </>
  );
}

export function TbStatements({
  path,
  layer,
  unit,
}: {
  path: Path;
  layer: "unadjusted" | "final";
  unit: string;
}): JSX.Element {
  const statements = useQuery({
    ...statementsOptions({ ...path, query: { layer } }),
    retry: false,
  });
  if (statements.isPending) return <Skeleton className="m-4 h-60" />;
  if (statements.isError)
    return <Alert title="Statements aren't available">{errorMessage(statements.error)}</Alert>;
  const s = statements.data;
  if (s == null) {
    return (
      <p className="p-4 text-[13px] text-ink-3">Map the trial balance first (the Mapping view).</p>
    );
  }
  const hasPrior = s.py_totals != null;
  const head = (title: string) => (
    <thead className="bg-band-hd text-ink-3">
      <tr>
        <th scope="col" className="px-3 py-1.5 text-left font-medium">
          {title}
        </th>
        <th scope="col" className="px-3 py-1.5 text-right font-medium">
          Current year
        </th>
        {hasPrior && (
          <th scope="col" className="px-3 py-1.5 text-right font-medium">
            Prior year
          </th>
        )}
      </tr>
    </thead>
  );
  return (
    <div className="flex flex-col gap-3 p-4 text-[12.5px]">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone="neutral">{`Draft · ${layer === "final" ? "Final" : "Unadjusted"}`}</StatusPill>
        {s.balanced ? (
          <StatusPill tone="success">Balance sheet balances</StatusPill>
        ) : (
          <StatusPill tone="danger">{`Balance sheet off ${amount(s.difference, unit)}`}</StatusPill>
        )}
        {s.unmapped > 0 && (
          <StatusPill tone="warning">{`${String(s.unmapped)} accounts unmapped`}</StatusPill>
        )}
      </div>
      <table
        aria-label="Balance sheet"
        className="w-full border-collapse rounded-nested shadow-e1"
      >
        {head("Balance sheet")}
        <Section s={s} classes={["assets", "liabilities", "equity"]} unit={unit} />
        <tbody>
          <tr>
            <td className="px-3 py-1 text-ink-2">Current-year earnings</td>
            <td className="px-3 py-1 text-right tabular-nums">{amount(s.net_income, unit)}</td>
            {hasPrior && (
              <td className="px-3 py-1 text-right tabular-nums text-ink-3">
                {amount(s.py_net_income, unit)}
              </td>
            )}
          </tr>
        </tbody>
      </table>
      <table
        aria-label="Income statement"
        className="w-full border-collapse rounded-nested shadow-e1"
      >
        {head("Income statement")}
        <Section s={s} classes={["revenue", "expenses"]} unit={unit} />
        <tbody>
          <tr className="border-t-[0.5px] border-hair font-medium">
            <td className="px-3 py-1.5">Net income</td>
            <td className="px-3 py-1.5 text-right tabular-nums">{amount(s.net_income, unit)}</td>
            {hasPrior && (
              <td className="px-3 py-1.5 text-right tabular-nums text-ink-3">
                {amount(s.py_net_income, unit)}
              </td>
            )}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
