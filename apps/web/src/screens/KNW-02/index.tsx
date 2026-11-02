import type {
  AbacusModulesMethodologyContractStepOut as StepOut,
  ProgramOut,
  VersionStateOut,
} from "@abacus/api-client";
import {
  approveVersionMutation,
  flagResolutionMutation,
  getVersionOptions,
  methodologyVersionDiffOptions,
  listTemplatesOptions,
  programStepsOptions,
  programStepsQueryKey,
  versionImportOptions,
  versionProgramsOptions,
  versionStateOptions,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  Dialog,
  EmptyState,
  ErrorState,
  EvidenceTriad,
  Icon,
  Pill,
  Sheet,
  SheetRow,
  MatchScope,
  Skeleton,
  SourceViewer,
  Tooltip,
  TriadTree,
  ValueRow,
  date,
  isoDate,
  time,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useRef, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { type WorkbookProblem, uploadMethodology, workbookProblems } from "../../domain/knowledge";
import { COPY } from "./copy";
import { ImportedStepRows, ParsingRunCard, importViewerFile } from "./ImportReview";
import { ActivityView, CompareMenu, DiffView, StandardsView } from "./Review";

// KNW-02 · Methodology versions, the workbook slice (K-01-T07; K-01 §3.2, §3.3; handoff KNW-02 e,
// f) on the T3 EvidenceTriad in its Prepare preset (tree 214 · viewer 571 · sheet 571):
//
//   tree    the version's programs with their step counts and open flags (the Programs band);
//           footer "Approve version…" (disabled with its tooltip while flags remain), then, once
//           approved, "Open program editor ›" (KNW-03, planned)
//   viewer  a workbook-only version has no source document: the empty state
//   sheet   "Parsed steps" for the picked program: number, text, the mandatory lock
//   e       `?ov=approve`: the O3 sheet: effective date, applies to, supersedes, the checklist the
//           server computed, "Approve version" (fresh MFA; human-only, INV-1)
//   f       approved: the green pill "Approved · Jan 12, 2026 2:31 PM · Margaret Okonkwo"
//
// "+ Upload methodology…" (fresh MFA) sends a v2 workbook as a new version; a refusal lists each
// row problem as sheet · row · column with a fixed message, never the cell's value (ADR-052).
// Approve is the server's to allow (`allowed_actions`); an agent never sees it (INV-1).
//
// K-01-T19 (KNW-02 c, d; AC6.1 to AC6.4): the tabs Import review · Diff vs v2 (its count) ·
// Standards mapping · Activity, the last three in one wide pane beside the Programs tree
// (`Review.tsx`); "Compare with v2 ⌄" picks the version the diff reads against (default: the
// version drafted from, else the one before). A draft from the program editor (Hannah's v4) opens
// in draft-review mode: the Programs band, the viewer's "edited in the program editor" empty
// state, and Diff, Standards and Approve working.

export type Knw02Tab = "review" | "diff" | "standards" | "activity";

export interface Knw02Search {
  program?: string | undefined;
  ov?: string | undefined;
  /** K-01-T19: Import review (default), Diff, Standards mapping, Activity. */
  tab?: Knw02Tab | undefined;
  /** The version the diff compares against ("Compare with v2"). */
  against?: string | undefined;
  /** K-01-T23 (KNW-02 a2): the ⚑ filter across programs. */
  flagged?: boolean | undefined;
}

export interface KNW02Props {
  versionId: string;
  search: Knw02Search;
  onSearch: (next: Knw02Search) => void;
  onBack?: () => void;
  /** "Open program editor ›" (KNW-03). */
  onOpenEditor?: (programId: string) => void;
  /** After an upload: the new version. */
  onOpenVersion?: (versionId: string) => void;
}

type Problem = { detail?: unknown } | null | undefined;
const detailOf = (error: unknown): string | undefined => {
  const detail = (error as Problem)?.detail;
  return typeof detail === "string" ? detail : undefined;
};

/** The first day of the month the clock is in, in the firm's zone: the effective date the sheet
 * proposes ("2026-01-01" on Jan 12, 2026). */
function firstOfMonth(now: Date): string {
  return `${isoDate(now, DEFAULT_TZ).slice(0, 7)}-01`;
}

/** The day before an ISO date ("2026-01-01" → "2025-12-31"). */
function dayBefore(iso: string): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

const dayWords = (iso: string, now: Date): string =>
  date(`${iso}T17:00:00Z`, { now, tz: DEFAULT_TZ, withYear: true });

function statusPill(state: VersionStateOut, now: Date): JSX.Element {
  if (state.status === "published" && state.approved_at != null) {
    const at = `${date(state.approved_at, { now, tz: DEFAULT_TZ, withYear: true })} ${time(state.approved_at, { tz: DEFAULT_TZ })}`;
    return (
      <Pill variant="green-tint" check>
        {COPY.status.approved(at, state.approved_by_name ?? "")}
      </Pill>
    );
  }
  if (state.status === "published")
    return <Pill variant="green-tint">{COPY.status.published}</Pill>;
  const words = COPY.status[state.status];
  return <Pill variant={state.status === "superseded" ? "neutral" : "amber"}>{words}</Pill>;
}

function ApproveSheet({
  state,
  name,
  prior,
  onClose,
  onStepUp,
}: {
  state: VersionStateOut;
  name: string;
  prior: VersionStateOut | undefined;
  onClose: () => void;
  onStepUp: () => void;
}): JSX.Element {
  const now = useNow();
  const queries = useQueryClient();
  const [effective, setEffective] = useState(() => firstOfMonth(now));
  const [refused, setRefused] = useState<string | null>(null);
  const approve = useMutation({
    ...approveVersionMutation(),
    onSuccess: async () => {
      await queries.invalidateQueries();
      onClose();
    },
    onError: (error) => {
      const detail = detailOf(error);
      if (detail === "forbidden") onStepUp();
      else if (detail === "flags_open") setRefused(COPY.approve.flagsOpen);
      else if (detail === "checklist_changed") setRefused(COPY.approve.checklistChanged);
      else if (detail === "unverified_sources") setRefused(COPY.approve.unverified);
      else setRefused(COPY.refused);
    },
  });
  const ready = (state.checklist ?? []).every((c) => c.ok) && state.checklist_hash != null;
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.approve.title(`${name} ${state.label}`)}
      footer={
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {COPY.approve.cancel}
          </Button>
          <Button
            disabled={!ready || approve.isPending}
            onClick={() => {
              approve.mutate({
                path: { version_id: state.version_id },
                body: {
                  effective_from: effective,
                  checklist_hash: state.checklist_hash ?? "",
                  row_version: state.row_version,
                },
              });
            }}
          >
            {COPY.approve.confirm}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-[10px]">
        <ValueRow
          kind="text"
          label={COPY.approve.effective}
          value={effective}
          onChange={setEffective}
          help={dayWords(effective, now)}
        />
        <SheetRow label={COPY.approve.appliesTo} value={COPY.approve.appliesValue} />
        {prior !== undefined && (
          <SheetRow
            label={COPY.approve.supersedes}
            value={COPY.approve.supersedesValue(prior.label, dayWords(dayBefore(effective), now))}
          />
        )}
        <section aria-label={COPY.approve.checklist} className="flex flex-col gap-[4px]">
          <h3 className="text-section font-medium">{COPY.approve.checklist}</h3>
          <ul className="flex flex-col gap-[4px] text-dense">
            {(state.checklist ?? []).map((c) => (
              <li key={c.code} className="flex items-center gap-[6px]">
                <Icon name={c.ok ? "check" : "x"} size={13} />
                {(COPY.approve.checks[c.code] ?? (() => c.code))(c.n)}
              </li>
            ))}
          </ul>
        </section>
        {refused !== null && (
          <p role="alert" className="text-dense text-red-ink">
            {refused}
          </p>
        )}
      </div>
    </Sheet>
  );
}

function UploadSheet({
  name,
  onClose,
  onUploaded,
  onStepUp,
}: {
  name: string;
  onClose: () => void;
  onUploaded: (versionId: string) => void;
  onStepUp: () => void;
}): JSX.Element {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [problems, setProblems] = useState<WorkbookProblem[] | null>(null);
  const [failed, setFailed] = useState(false);
  const upload = useMutation({
    mutationFn: async (chosen: File) => uploadMethodology(name, chosen),
    onSuccess: onUploaded,
    onError: (error) => {
      if (detailOf(error) === "forbidden") {
        onStepUp();
        return;
      }
      const found = workbookProblems(error);
      setProblems(found);
      setFailed(found === null);
    },
  });
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.upload.title}
      description={COPY.upload.help}
      footer={
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {COPY.approve.cancel}
          </Button>
          <Button
            disabled={file === null || upload.isPending}
            onClick={() => {
              if (file !== null) upload.mutate(file);
            }}
          >
            {COPY.upload.confirm}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-[10px]">
        <input
          ref={input}
          type="file"
          accept=".xlsx"
          aria-label={COPY.upload.file}
          className="sr-only"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setProblems(null);
            setFailed(false);
          }}
        />
        <ValueRow kind="value" label={COPY.upload.file}>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              input.current?.click();
            }}
          >
            {file?.name ?? COPY.upload.choose}
          </Button>
        </ValueRow>
        {problems !== null && (
          <section role="alert" aria-label={COPY.upload.problems(problems.length)}>
            <h3 className="text-section font-medium">{COPY.upload.problems(problems.length)}</h3>
            <ul className="flex flex-col gap-[2px] text-dense">
              {problems.map((p, n) => (
                <li key={`${p.where}:${String(n)}`} className="flex gap-[8px]">
                  <span className="font-medium">{p.where}</span>
                  <span className="text-ink-2">{p.message}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        {failed && (
          <p role="alert" className="text-dense text-red-ink">
            {COPY.upload.failed}
          </p>
        )}
      </div>
    </Sheet>
  );
}

function StepRows({ steps }: { steps: readonly StepOut[] }): JSX.Element {
  return (
    <table className="w-full table-fixed text-body">
      <tbody>
        {steps.map((s) => (
          <tr key={s.id} className="h-[42px] align-top hairline-b">
            <td className="w-[40px] px-[10px] py-[6px] text-ink-3">{s.number}</td>
            <td className="px-[6px] py-[6px]">
              <span className="line-clamp-2">{s.text}</span>
            </td>
            <td className="w-[90px] px-[6px] py-[6px] text-meta text-ink-3">
              {COPY.sheet.workbook}
            </td>
            <td className="w-[28px] py-[6px]">
              {s.mandatory && <Icon name="lock" size={12} label={COPY.sheet.mandatory} />}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function KNW02({
  versionId,
  search,
  onSearch,
  onBack,
  onOpenEditor,
  onOpenVersion,
}: KNW02Props): JSX.Element {
  const now = useNow();
  const path = { path: { version_id: versionId } };
  const state = useQuery(versionStateOptions(path));
  const version = useQuery(getVersionOptions(path));
  const templates = useQuery(listTemplatesOptions());
  const programs = useQuery({ ...versionProgramsOptions(path), retry: false });
  const list: readonly ProgramOut[] = programs.data ?? [];
  const picked = list.find((p) => p.id === search.program) ?? list[0];
  const steps = useQuery({
    ...programStepsOptions({ path: { program_id: picked?.id ?? "" } }),
    enabled: picked !== undefined,
    retry: false,
  });
  const priorId = (templates.data ?? []).find(
    (t) =>
      version.data !== undefined &&
      t.template_id === version.data.summary.template_id &&
      t.version === version.data.summary.version - 1,
  )?.version_id;
  const prior = useQuery({
    ...versionStateOptions({ path: { version_id: priorId ?? "" } }),
    enabled: priorId !== undefined,
  });
  const [stepUp, setStepUp] = useState(false);
  const set = (patch: Partial<Knw02Search>): void => {
    onSearch({ ...search, ...patch });
  };
  const draftedFrom = state.data?.drafted_from_version_id ?? undefined;
  const others = (templates.data ?? [])
    .filter(
      (t) =>
        version.data !== undefined &&
        t.template_id === version.data.summary.template_id &&
        t.version_id !== versionId,
    )
    .sort((a, b) => b.version - a.version);
  const againstId = search.against ?? draftedFrom ?? priorId;
  const againstLabel = `v${String(others.find((t) => t.version_id === againstId)?.version ?? "")}`;
  const diff = useQuery({
    ...methodologyVersionDiffOptions({
      path: { version_id: versionId },
      ...(search.against === undefined ? {} : { query: { against: search.against } }),
    }),
    retry: false,
  });
  const diffCount =
    diff.data === undefined
      ? undefined
      : diff.data.tiles.added + diff.data.tiles.changed + diff.data.tiles.removed;
  const tab: Knw02Tab = search.tab ?? "review";
  // K-01-T23 (KNW-02 a, a2, b): a version made by an import shows its file and parsed steps; while
  // the importer runs, the RunCard polls the import's own progress.
  const imported = useQuery({
    ...versionImportOptions(path),
    retry: false,
    refetchInterval: (q) => (q.state.data?.status === "parsing" ? 2000 : false),
  });
  const imp = imported.data;
  const cache = useQueryClient();
  const confirm = useMutation({
    ...flagResolutionMutation(),
    onSuccess: () =>
      cache.invalidateQueries({
        queryKey: programStepsQueryKey({ path: { program_id: picked?.id ?? "" } }),
      }),
  });

  if (state.isError) {
    return (
      <ErrorState
        title={COPY.error}
        onRetry={() => {
          void state.refetch();
        }}
      />
    );
  }
  const s = state.data;
  const name = version.data?.summary.template_name ?? "";
  if (s === undefined) return <Skeleton />;

  const family = name.split(" · ").at(-1) ?? name;
  const tabLabels: Readonly<Record<Knw02Tab, string>> = {
    review: COPY.tabs.review,
    diff: COPY.tabs.diff(againstLabel),
    standards: COPY.tabs.standards,
    activity: COPY.tabs.activity,
  };
  const wide =
    tab === "diff"
      ? {
          title: COPY.diff.title(againstLabel),
          children: (
            <DiffView
              versionId={versionId}
              against={search.against}
              label={s.label}
              againstLabel={againstLabel}
            />
          ),
        }
      : tab === "standards"
        ? {
            title: COPY.standards.title,
            children: (
              <StandardsView
                state={s}
                family={family}
                priorLabel={prior.data?.label ?? againstLabel}
              />
            ),
          }
        : tab === "activity"
          ? { title: COPY.activity.title, children: <ActivityView versionId={versionId} /> }
          : undefined;
  const flags = list.reduce((n, p) => n + p.flags_open, 0);
  const totalSteps = list.reduce((n, p) => n + p.step_count, 0);
  const canApprove = s.allowed_actions.includes("approve") && s.status === "needs_review";
  const canManage = s.allowed_actions.includes("manage");
  const approved = s.status === "published";

  const footer = (stacked: boolean): JSX.Element =>
    approved ? (
      PLANNED_VISIBLE && picked !== undefined ? (
        <Button
          variant="secondary"
          size="footer"
          className="w-full"
          onClick={() => {
            onOpenEditor?.(picked.id);
          }}
        >
          {COPY.footer.openEditor}
        </Button>
      ) : (
        <span />
      )
    ) : (
      <div className={stacked ? "flex flex-col gap-[8px]" : "flex gap-[8px]"}>
        {canApprove &&
          (flags > 0 ? (
            <Tooltip content={COPY.footer.resolveFirst(flags)}>
              <span className="w-full">
                <Button size="footer" disabled className="w-full">
                  {COPY.footer.approve}
                </Button>
              </span>
            </Tooltip>
          ) : (
            <Button
              size="footer"
              opensDialog
              className="w-full"
              onClick={() => {
                set({ ov: "approve" });
              }}
            >
              {COPY.footer.approve}
            </Button>
          ))}
      </div>
    );

  return (
    <MatchScope>
      <EvidenceTriad
        embedded
        toolbar={{ nav: [], active: "Knowledge", firm: "" }}
        record={{
          title: name,
          context: s.label,
          left: (
            <Button variant="secondary" size="sm" icon="chevron-left" onClick={onBack}>
              {COPY.back}
            </Button>
          ),
          right: (
            <span className="flex items-center gap-[8px]">
              {others.length > 0 && (
                <CompareMenu
                  label={againstLabel}
                  versions={others.map((t) => ({
                    id: t.version_id,
                    label: `v${String(t.version)}`,
                    current: t.version_id === againstId,
                  }))}
                  onPick={(id) => {
                    set({ against: id, tab: "diff" });
                  }}
                />
              )}
              {statusPill(s, now)}
              {canManage && (
                <Button
                  variant="secondary"
                  size="sm"
                  opensDialog
                  onClick={() => {
                    set({ ov: "upload" });
                  }}
                >
                  {COPY.footer.upload}
                </Button>
              )}
            </span>
          ),
        }}
        tabs={{
          options: (Object.keys(tabLabels) as Knw02Tab[]).map((k) =>
            k === "diff" && diffCount !== undefined
              ? { label: tabLabels[k], count: diffCount }
              : tabLabels[k],
          ),
          active: tabLabels[tab],
          label: COPY.tabsLabel,
          onChange: (label) => {
            const next = (Object.keys(tabLabels) as Knw02Tab[]).find(
              (k) => tabLabels[k] === label,
            );
            if (next !== undefined) set({ tab: next === "review" ? undefined : next });
          },
        }}
        {...(wide === undefined ? {} : { wide })}
        defaultPreset="prepare"
        tree={{
          title: COPY.tree.title,
          body: programs.isError ? (
            <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.tree.unavailable}</p>
          ) : (
            <TriadTree
              groups={[
                // K-01-T23 (KNW-02 a, a2, b): the files the import read, above the programs.
                ...(imp === undefined
                  ? []
                  : [
                      {
                        id: "files",
                        label: COPY.importReview.files,
                        subs: [
                          {
                            id: "uploaded",
                            label: name,
                            docs: imp.files.map((f) => ({
                              id: f.id,
                              label: f.filename,
                              checkable: false,
                            })),
                          },
                        ],
                      },
                    ]),
                {
                  id: "programs",
                  label: COPY.tree.programs(totalSteps),
                  subs: [
                    {
                      id: "all",
                      label: name,
                      docs: list.map((p) => ({
                        id: p.id,
                        label: `${p.code} ${p.name} ${String(p.step_count)}`,
                        checkable: false,
                        ...(p.flags_open > 0 ? { flags: p.flags_open } : {}),
                      })),
                    },
                  ],
                },
              ]}
              selected={picked?.id ?? null}
              onSelect={(doc) => {
                if (!list.some((p) => p.id === doc.id)) return; // a file row selects no program
                set({ program: doc.id });
              }}
            />
          ),
          footer,
        }}
        viewer={
          imp !== undefined && imp.status !== "parsing" && steps.data !== undefined ? (
            <SourceViewer file={importViewerFile(versionId, imp, steps.data)} scrollToLit />
          ) : (
            <div className="flex flex-1 items-center justify-center p-[24px]">
              {s.drafted_from_version_id != null ? (
                <EmptyState icon="pencil" title={COPY.viewer.draft} />
              ) : (
                <EmptyState icon="file-spreadsheet" title={COPY.viewer.workbook}>
                  {COPY.viewer.workbookHelp}
                </EmptyState>
              )}
            </div>
          )
        }
        sheet={{
          tabs: imp === undefined ? [COPY.sheet.tab] : [COPY.sheet.tab, COPY.importReview.flagged],
          active: search.flagged === true ? COPY.importReview.flagged : COPY.sheet.tab,
          onTab: (label) => {
            set({ flagged: label === COPY.importReview.flagged ? true : undefined });
          },
          children:
            picked === undefined ? (
              <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.sheet.empty}</p>
            ) : (
              <div className="flex min-h-full flex-col">
                {imp?.status === "parsing" && <ParsingRunCard imp={imp} />}
                <div className="flex-1">
                  {steps.data === undefined ? (
                    <Skeleton />
                  ) : imp !== undefined ? (
                    <ImportedStepRows
                      steps={steps.data}
                      flaggedOnly={search.flagged === true}
                      {...(canManage && s.status !== "published"
                        ? {
                            onConfirm: (step: StepOut) => {
                              confirm.mutate({
                                path: { version_id: versionId, step_id: step.id },
                                body: { action: "confirm", row_version: step.row_version },
                              });
                            },
                          }
                        : {})}
                    />
                  ) : (
                    <StepRows steps={steps.data} />
                  )}
                </div>
                <p className="h-[30px] px-[12px] text-meta leading-[30px] text-ink-3">
                  {COPY.sheet.footer(picked.step_count, picked.mandatory_count, picked.flags_open)}
                </p>
              </div>
            ),
        }}
      />
      {search.ov === "approve" && canApprove && flags === 0 && (
        <ApproveSheet
          state={s}
          name={name}
          prior={prior.data}
          onClose={() => {
            set({ ov: undefined });
          }}
          onStepUp={() => {
            setStepUp(true);
          }}
        />
      )}
      {search.ov === "upload" && canManage && (
        <UploadSheet
          name={name}
          onClose={() => {
            set({ ov: undefined });
          }}
          onUploaded={(id) => {
            set({ ov: undefined });
            onOpenVersion?.(id);
          }}
          onStepUp={() => {
            setStepUp(true);
          }}
        />
      )}
      <Dialog
        open={stepUp}
        onOpenChange={setStepUp}
        title={COPY.stepUp.title}
        description={COPY.stepUp.body}
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setStepUp(false);
            }}
          >
            {COPY.stepUp.cancel}
          </Button>
          <Button
            onClick={() => {
              signIn(currentRoute(), { forceLogin: true });
            }}
          >
            {COPY.stepUp.signIn}
          </Button>
        </div>
      </Dialog>
    </MatchScope>
  );
}
