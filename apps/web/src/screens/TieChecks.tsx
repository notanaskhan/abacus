import type {
  RollforwardComponentBody,
  TieOutCheckBody,
  TieOutCheckOut,
} from "@abacus/api-client";
import {
  defineCheckMutation,
  listEvidenceVersionsOptions,
  tieOutChecksOptions,
  tieOutChecksQueryKey,
} from "@abacus/api-client/query";
import { Button, Fieldset, Sheet, StatusPill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { amount } from "./amounts";

// SPEC-310 (TASK-321): tie-out checks on the trial balance. The server computes every result
// (tie · off n · Pending) on read from the current version; an expected value must cite the
// document it came from.

const KIND_WORD: Record<TieOutCheckOut["kind"], string> = {
  balanced: "Balances",
  tie: "Ties to a document",
  rollforward: "Rollforward",
};

export function checkWord(c: TieOutCheckOut): {
  label: string;
  tone: "success" | "warning" | "neutral";
} {
  if (c.result.status === "tie") return { label: "tie", tone: "success" };
  if (c.result.status === "off")
    return { label: `off ${amount(c.result.difference)}`, tone: "warning" };
  return { label: "Pending", tone: "neutral" };
}

function title(c: TieOutCheckOut): string {
  if (c.result.formula != null) return c.result.formula;
  if (c.result.missing.length > 0)
    return `Not in this trial balance: ${c.result.missing.join(", ")}`;
  if (c.result.actual != null && c.result.expected != null)
    return `${amount(c.result.actual)} against ${amount(c.result.expected)}`;
  return KIND_WORD[c.kind];
}

export function CheckStrip({
  engagementId,
  tbId,
  canDefine,
  selected,
}: {
  engagementId: string;
  tbId: string;
  canDefine: boolean;
  selected: string[];
}): JSX.Element {
  const path = { path: { engagement_id: engagementId, tb_id: tbId } };
  const checks = useQuery({ ...tieOutChecksOptions(path), retry: false });
  const [adding, setAdding] = useState(false);
  return (
    <div
      aria-label="Checks"
      className="flex flex-wrap items-center gap-2 border-b-[0.5px] border-hair px-4 py-2 text-[12.5px]"
    >
      <span className="font-medium text-ink-2">Checks</span>
      {(checks.data ?? []).length === 0 && !checks.isPending && (
        <span className="text-ink-3">None yet.</span>
      )}
      {(checks.data ?? []).map((c) => {
        const word = checkWord(c);
        return (
          <span key={c.id} title={title(c)} className="inline-flex items-center gap-1.5">
            <span className="text-ink-2">{c.label}</span>
            <StatusPill tone={word.tone}>{word.label}</StatusPill>
          </span>
        );
      })}
      <span className="flex-1" />
      {canDefine && (
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            setAdding(true);
          }}
        >
          Add check
        </Button>
      )}
      {adding && (
        <CheckSheet
          engagementId={engagementId}
          tbId={tbId}
          selected={selected}
          onClose={() => {
            setAdding(false);
          }}
        />
      )}
    </div>
  );
}

type Row = { label: string; sign: 1 | -1; value: string };
const AMOUNT = /^-?\d{1,16}(\.\d{1,2})?$/;

/** The body the server takes, or null while the form is incomplete (exported for tests). */
export function checkBody(form: {
  label: string;
  kind: TieOutCheckBody["kind"];
  accounts: string;
  column: "eoy" | "boy";
  negate: boolean;
  expected: string;
  rows: Row[];
  citation: string;
}): TieOutCheckBody | null {
  const label = form.label.trim();
  if (label === "") return null;
  if (form.kind === "balanced") return { label, kind: "balanced", column: form.column };
  const accounts = form.accounts
    .split(/[\s,]+/)
    .map((a) => a.trim())
    .filter(Boolean);
  if (accounts.length === 0 || form.citation === "") return null;
  const base = {
    label,
    kind: form.kind,
    accounts,
    column: form.column,
    negate: form.negate,
    citation_ids: [form.citation],
  };
  if (form.kind === "tie") {
    const expected = form.expected.replace(/,/g, "").trim();
    return AMOUNT.test(expected) ? { ...base, expected } : null;
  }
  const components: RollforwardComponentBody[] = [];
  for (const r of form.rows) {
    const value = r.value.replace(/,/g, "").trim();
    if (r.label.trim() === "" || !AMOUNT.test(value)) return null;
    components.push({ label: r.label.trim(), sign: r.sign, value });
  }
  return components.length > 0 ? { ...base, components } : null;
}

function CheckSheet({
  engagementId,
  tbId,
  selected,
  onClose,
}: {
  engagementId: string;
  tbId: string;
  selected: string[];
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, tb_id: tbId } };
  const evidence = useQuery({
    ...listEvidenceVersionsOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<TieOutCheckBody["kind"]>("tie");
  const [accounts, setAccounts] = useState(selected.join(", "));
  const [column, setColumn] = useState<"eoy" | "boy">("eoy");
  const [negate, setNegate] = useState(false);
  const [expected, setExpected] = useState("");
  const [rows, setRows] = useState<Row[]>([{ label: "Beginning balance", sign: 1, value: "" }]);
  const [citation, setCitation] = useState("");
  const define = useMutation({
    ...defineCheckMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(tieOutChecksQueryKey(path), data);
      onClose();
    },
    onError: (e) => {
      const code = errorMessage(e);
      toast.show(code === "citation_required" ? "An expected value needs its source." : code);
    },
  });
  const body = checkBody({ label, kind, accounts, column, negate, expected, rows, citation });
  const input = "h-[30px] rounded-tile border-0 bg-nested px-2.5 text-[13px] inset-shadow-hair";
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title="Add check"
      footer={
        <Button
          disabled={body === null || define.isPending}
          onClick={() => {
            if (body !== null) define.mutate({ ...path, body });
          }}
        >
          Add
        </Button>
      }
    >
      <Fieldset>
        <div className="flex flex-col gap-2 text-[13px]">
          <label className="flex items-center justify-between gap-3">
            Name
            <input
              value={label}
              maxLength={120}
              placeholder="Net assets ↔ trust report"
              onChange={(e) => {
                setLabel(e.target.value);
              }}
              className={`${input} w-[260px]`}
            />
          </label>
          <div role="group" aria-label="Kind" className="flex gap-1">
            {(["balanced", "tie", "rollforward"] as const).map((k) => (
              <Button
                key={k}
                size="sm"
                variant={kind === k ? "default" : "outline"}
                aria-pressed={kind === k}
                onClick={() => {
                  setKind(k);
                }}
              >
                {KIND_WORD[k]}
              </Button>
            ))}
          </div>
          <label className="flex items-center justify-between gap-3">
            Column
            <select
              value={column}
              onChange={(e) => {
                setColumn(e.target.value === "boy" ? "boy" : "eoy");
              }}
              className={input}
            >
              <option value="eoy">End of year</option>
              <option value="boy">Beginning of year</option>
            </select>
          </label>
        </div>
      </Fieldset>
      {kind !== "balanced" && (
        <>
          <Fieldset title="Accounts">
            <input
              aria-label="Account codes"
              value={accounts}
              placeholder="1000, 1010"
              onChange={(e) => {
                setAccounts(e.target.value);
              }}
              className={`${input} w-full`}
            />
            <label className="mt-2 flex items-center gap-2 text-[12.5px]">
              <input
                type="checkbox"
                checked={negate}
                onChange={(e) => {
                  setNegate(e.target.checked);
                }}
              />
              Credit balance: compare as a positive amount
            </label>
          </Fieldset>
          {kind === "tie" ? (
            <Fieldset title="Expected">
              <input
                aria-label="Expected amount"
                value={expected}
                placeholder="16,812,400.00"
                onChange={(e) => {
                  setExpected(e.target.value);
                }}
                className={`${input} w-[200px] tabular-nums`}
              />
            </Fieldset>
          ) : (
            <Fieldset title="Rollforward">
              <div className="flex flex-col gap-1.5">
                {rows.map((r, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <select
                      aria-label={`Sign ${String(i + 1)}`}
                      value={r.sign}
                      onChange={(e) => {
                        setRows(
                          rows.map((x, j) =>
                            j === i ? { ...x, sign: e.target.value === "-1" ? -1 : 1 } : x,
                          ),
                        );
                      }}
                      className={input}
                    >
                      <option value="1">+</option>
                      <option value="-1">−</option>
                    </select>
                    <input
                      aria-label={`Component ${String(i + 1)}`}
                      value={r.label}
                      maxLength={80}
                      onChange={(e) => {
                        setRows(
                          rows.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)),
                        );
                      }}
                      className={`${input} flex-1`}
                    />
                    <input
                      aria-label={`Amount ${String(i + 1)}`}
                      value={r.value}
                      onChange={(e) => {
                        setRows(
                          rows.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)),
                        );
                      }}
                      className={`${input} w-[130px] tabular-nums`}
                    />
                  </div>
                ))}
                {rows.length < 12 && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setRows([...rows, { label: "", sign: 1, value: "" }]);
                    }}
                  >
                    Add line
                  </Button>
                )}
              </div>
            </Fieldset>
          )}
          <Fieldset title="Source of the expected value">
            {(evidence.data ?? []).length === 0 ? (
              <p className="text-[12.5px] text-ink-3">
                No evidence on this engagement yet; the expected value needs its document.
              </p>
            ) : (
              <div className="flex max-h-[200px] flex-col gap-1 overflow-auto text-[13px]">
                {(evidence.data ?? []).map((v) => (
                  <label key={v.id} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="citation"
                      checked={citation === v.id}
                      onChange={() => {
                        setCitation(v.id);
                      }}
                    />
                    {`${v.source}, version ${String(v.version_no)}`}
                  </label>
                ))}
              </div>
            )}
          </Fieldset>
        </>
      )}
    </Sheet>
  );
}
