import type { CellOut, CellBody, WorkpaperDetailOut } from "@abacus/api-client";
import {
  citeMutation,
  listEvidenceVersionsOptions,
  meOptions,
  setCellsMutation,
  signOffEqrMutation,
  signOffManagerMutation,
  signOffPartnerMutation,
  signOffPrepareMutation,
  signOffReviewMutation,
  teamOptions,
  reviewNotesOptions,
  workpaperDetailOptions,
  workpaperDetailQueryKey,
  workpapersQueryKey,
} from "@abacus/api-client/query";
import { Alert, Button, Fieldset, Menu, Sheet, Skeleton, StatusPill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, type KeyboardEvent, useState } from "react";
import { errorMessage } from "../api";
import { groupDigits } from "./amounts";
import { openAnchors, ReviewableNotes } from "./ReviewableNotes";
import { initials, LEVEL_SHORT, statusWord } from "./Workpapers";

// SPEC-308 (TASK-319): one working paper. A grid (A-H) with a formula bar; the server computes
// every formula (ADR-050) and the grid shows its values. Tickmarks and evidence sources sit on
// cells; the sign-off rail signs the current content at each level and shows staleness.

type Tickmark = NonNullable<CellBody["tickmarks"]>[number];
const TICKS: { code: Tickmark; mark: string; label: string }[] = [
  { code: "agreed", mark: "✓", label: "Agreed to source" },
  { code: "footed", mark: "F", label: "Footed" },
  { code: "cross_footed", mark: "CF", label: "Cross-footed" },
  { code: "recalculated", mark: "R", label: "Recalculated" },
  { code: "traced", mark: "T", label: "Traced" },
  { code: "vouched", mark: "V", label: "Vouched" },
  { code: "exception", mark: "!", label: "Exception" },
];
const MARK = Object.fromEntries(TICKS.map((t) => [t.code, t.mark])) as Record<Tickmark, string>;
const COLUMNS = ["A", "B", "C", "D", "E", "F", "G", "H"];
const MIN_ROWS = 30;
const LEVEL_ROLES: Record<number, readonly string[]> = {
  1: ["manager", "senior", "staff"],
  2: ["engagement_partner", "manager", "senior"],
  3: ["engagement_partner", "manager"],
  4: ["engagement_partner"],
  5: ["reviewer"],
};
const LEVEL_TITLE: Record<number, string> = {
  1: "Preparer",
  2: "Reviewer",
  3: "Manager",
  4: "Partner",
  5: "Quality reviewer",
};
const EDITORS = new Set(["engagement_partner", "manager", "senior", "staff"]);

/** The grid's rows: at least 30, and five past the last used row. */
export function rowCount(cells: { cell_key: string }[]): number {
  const last = Math.max(0, ...cells.map((c) => Number(/\d+$/.exec(c.cell_key)?.[0] ?? 0)));
  return Math.max(MIN_ROWS, last + 5);
}

/** What a cell shows: the computed number, text, or the formula's error code. */
export function display(cell: CellOut | undefined): string {
  if (cell === undefined) return "";
  if (cell.value != null) return groupDigits(cell.value);
  return cell.text ?? "";
}

export function Workpaper({
  engagementId,
  workpaperId,
}: {
  engagementId: string;
  workpaperId: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, workpaper_id: workpaperId } };
  const detail = useQuery({ ...workpaperDetailOptions(path), retry: false });
  const team = useQuery({
    ...teamOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  const me = useQuery(meOptions());
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role ?? "";
  const [selected, setSelected] = useState("A1");
  const [draft, setDraft] = useState<string | null>(null);
  const [citing, setCiting] = useState(false);
  const fresh = (data: WorkpaperDetailOut): void => {
    queryClient.setQueryData(workpaperDetailQueryKey(path), data);
    void queryClient.invalidateQueries({
      queryKey: workpapersQueryKey({ path: { engagement_id: engagementId } }),
    });
  };
  const fail = (e: unknown): void => {
    const code = errorMessage(e);
    toast.show(
      code === "review_notes_open"
        ? "Clear the open review notes before signing as a reviewer."
        : code === "not_prepared"
          ? "The preparer signs first."
          : code === "preparer_cannot_review"
            ? "Someone other than the preparer reviews."
            : code === "already_signed"
              ? "You already signed this content at that level."
              : code === "forbidden"
                ? "Your role can't do that on this paper."
                : code,
    );
  };
  const save = useMutation({ ...setCellsMutation(), onSuccess: fresh, onError: fail });
  // SPEC-313: cells with an open review note get a marker (shares the panel's query).
  const notes = useQuery({
    ...reviewNotesOptions({
      path: { engagement_id: engagementId },
      query: { target_type: "workpaper", target_id: workpaperId },
    }),
    retry: false,
  });
  const noted = openAnchors(notes.data);
  if (detail.isPending) return <Skeleton className="h-96" />;
  if (detail.isError) {
    return <Alert title="This working paper isn't available">{errorMessage(detail.error)}</Alert>;
  }
  const d = detail.data;
  const byKey = new Map(d.cells.map((c) => [c.cell_key, c]));
  const rows = rowCount(d.cells);
  const current = byKey.get(selected);
  const canEdit = EDITORS.has(role);
  const word = statusWord(d.workpaper);
  const commit = (key: string, raw: string | null, tickmarks?: Tickmark[]): void => {
    const old = byKey.get(key);
    const marks = tickmarks ?? old?.tickmarks ?? [];
    if ((old?.raw ?? "") === (raw ?? "") && tickmarks === undefined) return;
    save.mutate({ ...path, body: { cells: [{ cell_key: key, raw, tickmarks: marks }] } });
  };
  const move = (dc: number, dr: number): void => {
    const m = /^([A-Z]+)(\d+)$/.exec(selected);
    if (m === null) return;
    const c = Math.min(Math.max(COLUMNS.indexOf(m[1] ?? "A") + dc, 0), COLUMNS.length - 1);
    const r = Math.min(Math.max(Number(m[2]) + dr, 1), rows);
    setSelected(`${COLUMNS[c] ?? "A"}${String(r)}`);
  };
  const onGridKey = (e: KeyboardEvent<HTMLDivElement>): void => {
    if (draft !== null) return;
    const moves: Record<string, [number, number]> = {
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      Tab: [1, 0],
      Enter: [0, 1],
    };
    const step = moves[e.key];
    if (step !== undefined) {
      e.preventDefault();
      move(...step);
    } else if (canEdit && (e.key === "Delete" || e.key === "Backspace")) {
      e.preventDefault();
      commit(selected, null);
    } else if (canEdit && e.key.length === 1 && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      setDraft(e.key);
    }
  };
  const citationsHere = d.citations.filter((c) => c.cell_key === selected);
  return (
    <div className="grid items-start gap-3 xl:grid-cols-[1fr_300px]">
      <section
        aria-labelledby="wp-title"
        className="flex min-w-0 flex-col overflow-hidden rounded-pane bg-card shadow-e2"
      >
        <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
          <Link
            to="/engagements/$engagementId/workpapers"
            params={{ engagementId }}
            className="text-[12.5px] text-ink-3 hover:underline"
          >
            Working papers
          </Link>
          <span className="text-ink-4">/</span>
          <h2 id="wp-title" className="text-[15px] font-medium tracking-[-0.012em]">
            <span className="tabular-nums">{d.workpaper.code}</span> {d.workpaper.title}
          </h2>
          {d.workpaper.audit_area != null && (
            <span className="text-[12.5px] text-ink-3">{d.workpaper.audit_area}</span>
          )}
          <span className="flex-1" />
          <StatusPill tone={word.tone}>{word.label}</StatusPill>
        </div>
        <div className="flex items-center gap-2 border-b-[0.5px] border-hair px-3 py-1.5">
          <span className="w-[52px] text-center text-[12.5px] font-medium tabular-nums text-ink-2">
            {selected}
          </span>
          <span className="text-[12.5px] text-ink-4 italic">fx</span>
          <input
            aria-label={`Contents of ${selected}`}
            value={draft ?? current?.raw ?? ""}
            readOnly={!canEdit}
            maxLength={2000}
            onChange={(e) => {
              setDraft(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                commit(selected, draft ?? current?.raw ?? null);
                setDraft(null);
                move(0, 1);
              } else if (e.key === "Escape") {
                setDraft(null);
              }
            }}
            onBlur={() => {
              if (draft !== null) commit(selected, draft);
              setDraft(null);
            }}
            className="h-[26px] flex-1 rounded-tile border-0 bg-nested px-2 font-mono text-[12.5px] inset-shadow-hair"
          />
          {canEdit && (
            <Menu
              label="Tickmarks"
              trigger={
                <Button size="sm" variant="secondary">
                  Tickmark
                </Button>
              }
              sections={[
                TICKS.map((t) => {
                  const on = (current?.tickmarks ?? []).includes(t.code);
                  return {
                    label: `${on ? "Remove" : "Add"} ${t.mark} ${t.label}`,
                    onSelect: () => {
                      const marks = current?.tickmarks ?? [];
                      commit(
                        selected,
                        current?.raw ?? null,
                        on ? marks.filter((m) => m !== t.code) : [...marks, t.code],
                      );
                    },
                  };
                }),
              ]}
            />
          )}
          {canEdit && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setCiting(true);
              }}
            >
              Cite source
            </Button>
          )}
        </div>
        <div
          role="grid"
          aria-label={`${d.workpaper.code} cells`}
          aria-readonly={!canEdit}
          tabIndex={0}
          onKeyDown={onGridKey}
          className="max-h-[640px] overflow-auto focus:outline-none"
        >
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="sticky top-0 z-10 bg-band-hd">
              <tr>
                <th className="w-[40px] border-[0.5px] border-hair" />
                {COLUMNS.map((c) => (
                  <th
                    key={c}
                    scope="col"
                    className="min-w-[110px] border-[0.5px] border-hair py-1 font-medium text-ink-3"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: rows }, (_, i) => i + 1).map((r) => (
                <tr key={r}>
                  <th
                    scope="row"
                    className="border-[0.5px] border-hair bg-band-hd px-1 text-right font-medium text-ink-3 tabular-nums"
                  >
                    {r}
                  </th>
                  {COLUMNS.map((c) => {
                    const key = `${c}${String(r)}`;
                    const cell = byKey.get(key);
                    const cited = d.citations.some((x) => x.cell_key === key);
                    const isSel = key === selected;
                    const numeric = cell?.value != null;
                    return (
                      <td
                        key={key}
                        role="gridcell"
                        aria-selected={isSel}
                        title={cell?.formula === true ? (cell.raw ?? "") : undefined}
                        onClick={() => {
                          if (draft !== null) commit(selected, draft);
                          setDraft(null);
                          setSelected(key);
                        }}
                        className={
                          "relative h-[26px] border-[0.5px] border-hair px-1.5 whitespace-nowrap " +
                          (numeric ? "text-right tabular-nums " : "") +
                          (cell?.error === true ? "text-danger " : "") +
                          (isSel
                            ? "bg-sel-bg outline-[1.5px] outline-accent -outline-offset-1"
                            : "")
                        }
                      >
                        {isSel && draft !== null ? (
                          <input
                            autoFocus
                            aria-label={`Edit ${key}`}
                            value={draft}
                            maxLength={2000}
                            onChange={(e) => {
                              setDraft(e.target.value);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === "Tab") {
                                e.preventDefault();
                                e.stopPropagation();
                                commit(key, draft);
                                setDraft(null);
                                move(e.key === "Tab" ? 1 : 0, e.key === "Enter" ? 1 : 0);
                              } else if (e.key === "Escape") {
                                e.stopPropagation();
                                setDraft(null);
                              }
                            }}
                            className="absolute inset-0 w-full border-0 bg-card px-1.5 font-mono text-[12.5px]"
                          />
                        ) : (
                          <>
                            {display(cell)}
                            {(cell?.tickmarks.length ?? 0) > 0 && (
                              <span className="ml-1 text-[10.5px] font-medium text-accent">
                                {cell?.tickmarks.map((t) => MARK[t]).join(" ")}
                              </span>
                            )}
                            {noted.has(key) && (
                              <span
                                aria-label="Has an open review note"
                                className="absolute top-0 left-0 size-0 border-t-[6px] border-r-[6px] border-t-danger border-r-transparent"
                              />
                            )}
                            {cited && (
                              <span
                                aria-label="Has a source"
                                className="absolute top-0 right-0 size-0 border-t-[6px] border-l-[6px] border-t-accent border-l-transparent"
                              />
                            )}
                          </>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <aside className="flex flex-col gap-3">
        <SignOffRail
          detail={d}
          role={role}
          myName={team.data?.find((m) => m.user_id === me.data?.user_id)?.display_name ?? ""}
          path={path}
          onDone={fresh}
          onError={fail}
        />
        <section className="rounded-pane bg-card p-3 shadow-e2">
          <h3 className="mb-2 text-[13px] font-medium">{`Cell ${selected}`}</h3>
          {current === undefined ? (
            <p className="text-[12.5px] text-ink-3">Empty.</p>
          ) : (
            <p className="text-[12.5px] text-ink-3">{`Set by ${current.set_by_name}`}</p>
          )}
          {citationsHere.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1">
              {citationsHere.map((c, i) => (
                <li key={`${c.evidence_version_id}-${String(i)}`} className="text-[12.5px]">
                  <span className="mr-1.5 inline-flex size-[16px] items-center justify-center rounded-full bg-accent-soft text-[10.5px] font-medium tabular-nums">
                    {i + 1}
                  </span>
                  {c.locator ?? "Source document"}
                  <span className="text-ink-3">{` · ${c.added_by_name}`}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-labelledby="wp-notes" className="rounded-pane bg-card p-3 shadow-e2">
          <h3 id="wp-notes" className="mb-1 text-[13px] font-medium">
            Review notes
          </h3>
          <ReviewableNotes
            engagementId={engagementId}
            targetType="workpaper"
            targetId={workpaperId}
            anchor={selected}
            role={role}
          />
        </section>
        <section aria-labelledby="wp-tb" className="rounded-pane bg-card p-3 shadow-e2">
          <h3 id="wp-tb" className="mb-1 text-[13px] font-medium">
            Trial balance
          </h3>
          {d.trial_balance == null ? (
            <p className="text-[12.5px] text-ink-3">
              No trial balance adopted yet; TB() cells show #TB!.
            </p>
          ) : (
            <>
              <p className="text-[12px] text-ink-3 tabular-nums">
                {`${d.trial_balance.period_end} · v${String(d.trial_balance.version_no)} · type =TB("1000") in a cell`}
              </p>
              {d.tb_accounts.length === 0 ? (
                <p className="mt-1 text-[12.5px] text-ink-3">
                  {`No accounts carry WP ref ${d.workpaper.code} yet.`}
                </p>
              ) : (
                <ul className="mt-1.5 flex flex-col gap-0.5 text-[12.5px]">
                  {d.tb_accounts.map((a) => (
                    <li key={a.account_code}>
                      <button
                        type="button"
                        disabled={!canEdit}
                        title={
                          canEdit ? `Link ${selected} to account ${a.account_code}` : undefined
                        }
                        onClick={() => {
                          commit(selected, `=TB("${a.account_code}")`);
                        }}
                        className="flex w-full items-center gap-2 rounded-tile px-1 py-0.5 text-left hover:bg-nested disabled:hover:bg-transparent"
                      >
                        <span className="tabular-nums text-ink-3">{a.account_code}</span>
                        <span className="flex-1 truncate">{a.account_name}</span>
                        <span className="tabular-nums">{groupDigits(a.eoy)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
        <section className="rounded-pane bg-card p-3 shadow-e2">
          <h3 className="mb-2 text-[13px] font-medium">Versions</h3>
          {d.versions.length === 0 ? (
            <p className="text-[12.5px] text-ink-3">Each sign-off saves a version.</p>
          ) : (
            <ul className="flex flex-col gap-1 text-[12.5px]">
              {d.versions.map((v) => (
                <li key={v.version_no} className="flex items-center gap-2">
                  <span className="font-medium tabular-nums">{`v${String(v.version_no)}`}</span>
                  <span className="text-ink-3">{v.created_by_name}</span>
                  <span className="flex-1" />
                  <span className="font-mono text-[11px] text-ink-4" title={v.content_hash}>
                    {v.content_hash.slice(0, 8)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
      {citing && (
        <CiteSheet
          engagementId={engagementId}
          cellKey={selected}
          path={path}
          onClose={() => {
            setCiting(false);
          }}
          onDone={fresh}
          onError={fail}
        />
      )}
    </div>
  );
}

type Path = { path: { engagement_id: string; workpaper_id: string } };

function SignOffRail({
  detail,
  role,
  myName,
  path,
  onDone,
  onError,
}: {
  detail: WorkpaperDetailOut;
  role: string;
  myName: string;
  path: Path;
  onDone: (d: WorkpaperDetailOut) => void;
  onError: (e: unknown) => void;
}): JSX.Element {
  const opts = { onSuccess: onDone, onError };
  const sign = {
    1: useMutation({ ...signOffPrepareMutation(), ...opts }),
    2: useMutation({ ...signOffReviewMutation(), ...opts }),
    3: useMutation({ ...signOffManagerMutation(), ...opts }),
    4: useMutation({ ...signOffPartnerMutation(), ...opts }),
    5: useMutation({ ...signOffEqrMutation(), ...opts }),
  } as const;
  const empty = detail.cells.length === 0 && detail.citations.length === 0;
  const preparer = detail.workpaper.levels.find((l) => l.level === 1);
  const prepared = preparer?.signed_by_name != null && !preparer.stale;
  return (
    <section aria-labelledby="signoff-heading" className="rounded-pane bg-card p-3 shadow-e2">
      <h3 id="signoff-heading" className="mb-2 text-[13px] font-medium">
        Sign-offs
      </h3>
      <ul className="flex flex-col gap-1.5">
        {detail.workpaper.levels.map((l) => {
          const signed = l.signed_by_name != null;
          const mutation = sign[l.level as 1 | 2 | 3 | 4 | 5];
          const allowed = (LEVEL_ROLES[l.level] ?? []).includes(role);
          const current = signed && !l.stale;
          const blocked =
            empty ||
            (l.level > 1 && !prepared) ||
            (l.level === 2 && preparer?.signed_by_name === myName && !preparer.stale);
          return (
            <li key={l.level} className="flex items-center gap-2 text-[12.5px]">
              <span
                aria-hidden="true"
                className={
                  "inline-flex h-[20px] min-w-[28px] items-center justify-center rounded-[3px] text-[10.5px] font-medium " +
                  (signed
                    ? l.stale
                      ? "bg-amber-tint text-ink-2 line-through"
                      : "bg-green-tint text-ink"
                    : "bg-nested text-ink-4 inset-shadow-hair")
                }
              >
                {LEVEL_SHORT[l.name]}
              </span>
              <span className="flex flex-col">
                <span>{LEVEL_TITLE[l.level]}</span>
                <span className="text-[11.5px] text-ink-3">
                  {signed
                    ? `${l.signed_by_name ?? ""} · ${initials(l.signed_by_name)}${l.stale ? " · changed since" : ""}`
                    : "Not signed"}
                </span>
              </span>
              <span className="flex-1" />
              {allowed && !current && (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={blocked || mutation.isPending}
                  onClick={() => {
                    mutation.mutate({ ...path });
                  }}
                >
                  {l.stale ? "Sign again" : "Sign off"}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function CiteSheet({
  engagementId,
  cellKey,
  path,
  onClose,
  onDone,
  onError,
}: {
  engagementId: string;
  cellKey: string;
  path: Path;
  onClose: () => void;
  onDone: (d: WorkpaperDetailOut) => void;
  onError: (e: unknown) => void;
}): JSX.Element {
  const evidence = useQuery({
    ...listEvidenceVersionsOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  const [versionId, setVersionId] = useState("");
  const [locator, setLocator] = useState("");
  const cite = useMutation({
    ...citeMutation(),
    onSuccess: (d) => {
      onDone(d);
      onClose();
    },
    onError,
  });
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={`Cite a source on ${cellKey}`}
      footer={
        <Button
          disabled={versionId === "" || cite.isPending}
          onClick={() => {
            cite.mutate({
              path: { ...path.path, cell_key: cellKey },
              body: {
                evidence_version_id: versionId,
                ...(locator.trim() === "" ? {} : { locator: locator.trim() }),
              },
            });
          }}
        >
          Cite
        </Button>
      }
    >
      <Fieldset title="Evidence on this engagement">
        {evidence.isPending ? (
          <Skeleton className="h-20" />
        ) : (evidence.data ?? []).length === 0 ? (
          <p className="text-[12.5px] text-ink-3">No evidence has been received yet.</p>
        ) : (
          <div className="flex max-h-[320px] flex-col gap-1 overflow-auto text-[13px]">
            {(evidence.data ?? []).map((v) => (
              <label key={v.id} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="evidence"
                  checked={versionId === v.id}
                  onChange={() => {
                    setVersionId(v.id);
                  }}
                />
                {`${v.source}, version ${String(v.version_no)}`}
                <span className="text-ink-3">{v.method}</span>
              </label>
            ))}
          </div>
        )}
      </Fieldset>
      <Fieldset title="Where in the document">
        <input
          value={locator}
          maxLength={120}
          placeholder="Page 2, or cell C9"
          aria-label="Where in the document"
          onChange={(e) => {
            setLocator(e.target.value);
          }}
          className="h-[30px] w-full rounded-tile border-0 bg-nested px-2.5 inset-shadow-hair"
        />
      </Fieldset>
    </Sheet>
  );
}
