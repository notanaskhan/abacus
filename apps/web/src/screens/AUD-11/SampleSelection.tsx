import type {
  CompletenessTieOut,
  SampleItemOut,
  SampleSetOut,
  SampleSetSummaryOut,
} from "@abacus/api-client";
import {
  sampleItemsOptions,
  sampleSetOptions,
  sampleSetsListOptions,
} from "@abacus/api-client/query";
import {
  Button,
  type CockpitCanvas,
  DEFAULT_TZ,
  Icon,
  PaneAction,
  Picker,
  Pill,
  SearchField,
  Segmented,
  StatusDisc,
  TallyPill,
  Tooltip,
  ValueRow,
  type ViewState,
  cn,
  count,
  date,
  dateTime,
  pct,
  prose,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { useSession } from "../../app-core/session";
import { COPY } from "./copy";

// AUD-11 · Sampling (A-03-T11; A-03 §5.1; docs/screens/AUD-11.md; handoff AUD-11 spec, R1, R2): the
// AUD-02 cockpit's Fieldwork › Sample Selection canvas, over the C9 sampling reads. States built
// here: a (approved), b (draft: Generate disabled with its tooltip), d (the size edited below the
// methodology: the amber banner and a required rationale), the composed sample-set picker and the
// C-20 states (off, loading, error, a walled person's 404). c, e and f are A-03-T15's.
//
// Every figure is the server's (ADR-050): counts, totals, tie results, the seed. No control here
// approves or draws for the agent; Approve and the draw are people's, and the version history
// shows only a person's approval chip (INV-1, INV-5).

const BLOCK = "mx-[12px] mt-[12px] overflow-hidden rounded-pane bg-card shadow-e1";
const ROW = "flex min-h-[33px] items-center gap-[8px] px-[12px] py-[5px] text-body hairline-b";

function Block({
  title,
  right,
  children,
}: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
}): JSX.Element {
  return (
    <section aria-label={title} data-aud11="block" className={BLOCK}>
      <header className="flex h-[32px] items-center gap-[8px] px-[12px] text-body font-medium hairline-b">
        <h3 className="flex-1">{title}</h3>
        {right}
      </header>
      {children}
    </section>
  );
}

function Kv({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div data-aud11="kv" className={ROW}>
      <span className="flex-none text-ink-2">{label}</span>
      <span className="ml-auto min-w-0 text-right">{children}</span>
    </div>
  );
}

/** "02/10/2025" from the ISO date, as the design prints a hire date (text, never arithmetic). */
function usDate(iso: string | null | undefined): string {
  if (iso == null) return "—";
  const [y, m, d] = iso.split("-");
  return `${m ?? ""}/${d ?? ""}/${y ?? ""}`;
}

function shortHash(sha: string): string {
  return `sha256 ${sha.slice(0, 4)}…${sha.slice(-4)}`;
}

function Tie({ tie, first }: { tie: CompletenessTieOut; first: boolean }): JSX.Element {
  const parts = tie.comparisons.map((c) => `${c.label} ${prose(c.amount)}`).join(" + ");
  const amount = tie.difference == null ? "" : prose(tie.difference.replace(/^-/u, ""));
  return (
    <span data-tie={tie.result} className="flex items-center justify-end gap-[6px]">
      <span>
        {first && tie.left_amount != null
          ? `${COPY.population.left(prose(tie.left_amount))} `
          : ""}
        {`= ${parts}`}
      </span>
      <TallyPill code={tie.result} vars={{ amount }} />
    </span>
  );
}

function Items({ set }: { set: SampleSetOut }): JSX.Element {
  const [q, setQ] = useState("");
  const items = useQuery(
    sampleItemsOptions({
      path: { sample_set_id: set.id, version_no: set.version_no },
      query: q === "" ? {} : { q },
    }),
  );
  const rows: SampleItemOut[] = items.data?.items ?? [];
  const excel = (set.allowed_actions ?? []).includes("sample_set.export");
  return (
    <Block
      title={COPY.items.title(set.items_total)}
      right={
        <>
          <SearchField
            label={COPY.items.search}
            placeholder={COPY.items.search}
            value={q}
            onChange={setQ}
            className="w-[160px]"
          />
          {excel && (
            <Button variant="ghost" size="sm">
              {COPY.items.excel}
            </Button>
          )}
        </>
      }
    >
      <ol data-aud11="items">
        {rows.map((item) => (
          <li
            key={item.position}
            data-item={item.record_key}
            className="flex h-[30px] items-center gap-[10px] px-[12px] text-body hairline-b hover:bg-nested"
          >
            <span className="w-[34px] flex-none text-meta text-ink-3 tabular-nums">
              {item.position}
            </span>
            <span className="min-w-0 flex-1 truncate">{item.name ?? item.record_key}</span>
            <span className="text-meta text-ink-3">{item.record_key}</span>
            <span className="w-[84px] text-right tabular-nums">{usDate(item.hire_date)}</span>
            <StatusDisc state="done" />
          </li>
        ))}
        {items.isSuccess && rows.length === 0 && (
          <li className="px-[12px] py-[10px] text-meta text-ink-3">{COPY.items.none}</li>
        )}
      </ol>
    </Block>
  );
}

function Versions({ set, tz }: { set: SampleSetOut; tz: string }): JSX.Element {
  return (
    <Block title={COPY.versions.title}>
      <ol>
        {set.versions.map((v) => {
          const superseded = v.status === "superseded";
          const line = COPY.versions.line(
            dateTime(v.created_at, { tz }),
            superseded ? null : v.created_by_name,
            v.seed_hex,
            v.population_label,
            v.record_count,
          );
          const off =
            v.tie_result === "off" && v.tie_difference != null
              ? `; ${COPY.versions.off(prose(v.tie_difference.replace(/^-/u, "")))}`
              : "";
          return (
            <li
              key={v.version_no}
              data-version={v.version_no}
              data-status={v.status}
              className="flex min-h-[44px] items-center gap-[8px] px-[12px] py-[6px] text-body hairline-b"
            >
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="font-medium">{COPY.version(v.version_no)}</span>
                <span className={cn("text-meta text-ink-3", superseded && "line-through")}>
                  {`${line.replace(/\)$/u, "")}${off})`}
                </span>
              </span>
              {v.status === "approved" && (
                <>
                  <Pill variant="green-tint" size="sm">
                    {COPY.versions.approved}
                  </Pill>
                  {v.approved != null && (
                    <Pill variant="neutral" size="sm" check>
                      {v.approved.initials}
                    </Pill>
                  )}
                </>
              )}
              {v.status === "draft" && (
                <Pill variant="neutral" size="sm">
                  {v.prepared == null
                    ? COPY.versions.draft
                    : COPY.versions.prepared(v.prepared.initials)}
                </Pill>
              )}
              {superseded && (
                <Pill variant="soon" size="sm" className="line-through">
                  {COPY.versions.superseded}
                </Pill>
              )}
            </li>
          );
        })}
      </ol>
    </Block>
  );
}

function Body({
  set,
  editing,
  size,
  onSize,
  rationale,
  onRationale,
  onCancel,
}: {
  set: SampleSetOut;
  editing: boolean;
  size: number;
  onSize: (n: number) => void;
  rationale: string;
  onRationale: (text: string) => void;
  onCancel: () => void;
}): JSX.Element {
  const tz = useSession().tz ?? DEFAULT_TZ;
  const now = useNow();
  const p = set.parameters;
  const pop = set.population;
  const src = pop.source;
  const below = editing && size < p.computed_size;
  return (
    <div data-aud11="body" className="pb-[12px]">
      <Block title={COPY.population.title}>
        <Kv label={COPY.population.source}>
          <Segmented
            label={COPY.population.source}
            size="small"
            active={
              src.kind === "upload" ? COPY.population.sources[0] : COPY.population.sources[1]
            }
            options={[
              { label: COPY.population.sources[0], disabled: src.kind !== "upload" },
              { label: COPY.population.sources[1], disabled: src.kind !== "general_ledger" },
              { label: COPY.population.sources[2], disabled: true },
            ]}
          />
        </Kv>
        {src.kind === "upload" && src.file_name != null && (
          <Kv label={COPY.population.file}>
            <span className="text-ink">{src.file_name}</span>{" "}
            <Icon name="arrow-right" size={12} className="inline text-ink-3" />{" "}
            <span className="text-ink-3">
              {src.file_version_no != null &&
              src.uploaded_on != null &&
              src.uploaded_by_name != null
                ? COPY.population.fileDetail(
                    src.file_version_no,
                    date(src.uploaded_on, { now, tz }),
                    src.uploaded_by_name,
                  )
                : ""}
            </span>
          </Kv>
        )}
        <Kv label={COPY.population.records}>{count(String(pop.record_count))}</Kv>
        <Kv label={COPY.population.hash}>
          <span className="text-ink-3">{shortHash(pop.sha256)}</span>
        </Kv>
        <Kv label={COPY.population.completeness}>
          <span className="flex flex-col items-end gap-[4px] py-[2px]">
            {pop.ties.map((t, i) => (
              <Tie key={t.id} tie={t} first={i === 0} />
            ))}
          </span>
        </Kv>
        <Kv label={COPY.population.samplingUnit}>{pop.sampling_unit}</Kv>
        {pop.deviation_definition != null && (
          <Kv label={COPY.population.deviation}>{pop.deviation_definition}</Kv>
        )}
      </Block>

      <Block title={COPY.method.title}>
        <Kv label={COPY.method.method}>{COPY.method.methods[p.method] ?? p.method}</Kv>
        {p.rmm != null && <Kv label={COPY.method.rmm}>{COPY.method.rmms[p.rmm] ?? p.rmm}</Kv>}
        {p.tolerable_rate != null && (
          <Kv label={COPY.method.tolerable}>{pct(p.tolerable_rate)}</Kv>
        )}
        {p.expected_rate != null && <Kv label={COPY.method.expected}>{pct(p.expected_rate)}</Kv>}
        {p.confidence != null && <Kv label={COPY.method.confidence}>{pct(p.confidence)}</Kv>}
        <Kv label={COPY.method.size}>
          {p.statistical_crosscheck_size != null &&
            p.confidence != null &&
            p.tolerable_rate != null &&
            p.expected_rate != null && (
              <span className="mr-[10px] text-meta text-ink-3">
                {COPY.method.crosscheck(
                  p.statistical_crosscheck_size,
                  pct(p.confidence),
                  pct(p.tolerable_rate),
                  pct(p.expected_rate),
                )}
              </span>
            )}
          <span className="font-medium">{editing ? size : p.final_size}</span>
        </Kv>
        {editing && (
          <ValueRow
            kind="text"
            label={COPY.override.size}
            value={String(size)}
            onChange={(text) => {
              onSize(Number.parseInt(text.replace(/\D/gu, ""), 10) || 0);
            }}
          />
        )}
        {below && (
          <div className="px-[12px] py-[8px] hairline-b">
            <p
              role="status"
              data-aud11="override"
              className="flex h-[32px] items-center gap-[8px] rounded-nested bg-amber-tint px-[12px] text-dense text-amber-ink"
            >
              <Icon name="triangle-alert" size={14} />
              {COPY.override.banner(p.computed_size)}
            </p>
            <ValueRow
              kind="paragraph"
              label={COPY.override.rationaleLabel}
              value={rationale}
              onChange={onRationale}
              rows={3}
            />
            <div className="mt-[8px] flex justify-end gap-[8px]">
              <Button variant="secondary" size="sm" onClick={onCancel}>
                {COPY.override.cancel}
              </Button>
              <Button variant="primary" size="sm" disabled={rationale.trim() === ""}>
                {COPY.override.save}
              </Button>
            </div>
          </div>
        )}
        <Kv label={COPY.method.seed}>
          <span className="inline-flex items-center gap-[6px] font-mono text-cell">
            {p.seed_hex}
            <button
              type="button"
              aria-label={COPY.method.copySeed(p.seed_hex)}
              onClick={() => {
                void navigator.clipboard.writeText(p.seed_hex);
              }}
              className="text-ink-3 hover:text-ink"
            >
              <Icon name="copy" size={12} />
            </button>
          </span>
        </Kv>
        <Kv label={COPY.method.algorithm}>
          {COPY.method.sampler(p.sampler_version, COPY.method.algorithms[p.method] ?? "")}
        </Kv>
      </Block>

      <Items set={set} />
      <Versions set={set} tz={tz} />
    </div>
  );
}

export interface SampleSelectionOptions {
  /** The canvas is on screen: the reads run only then (the cockpit calls the hook always). */
  active?: boolean;
  /** The sample set to open (`?sample=`); the work item's first otherwise. */
  sample?: string;
  /** AUD-11 d: the size edit open at this value. */
  editSize?: number;
  /** "Sign off…": the host opens SHL-12 (`?ov=signoff:sample_set_version:<id>:L1`). */
  onSignOff?: (sampleSetId: string, versionNo: number) => void;
}

/** AUD-11's canvas for the cockpit (AUD-02 renders it for `?section=sample_selection`). */
export function useSampleSelectionCanvas(
  workItemId: string,
  options: SampleSelectionOptions = {},
): CockpitCanvas {
  const on = useFlag("sampling.sample_sets") === true;
  const active = options.active ?? true;
  const sets = useQuery({
    ...sampleSetsListOptions({ path: { work_item_id: workItemId } }),
    enabled: on && active,
  });
  const [chosen, setChosen] = useState<string | undefined>(options.sample);
  const list: SampleSetSummaryOut[] = sets.data?.items ?? [];
  const current = chosen ?? list[0]?.id;
  const set = useQuery({
    ...sampleSetOptions({ path: { sample_set_id: current ?? "" } }),
    enabled: on && active && current !== undefined,
  });
  const [editing, setEditing] = useState(options.editSize !== undefined);
  const [size, setSize] = useState(options.editSize ?? set.data?.parameters.final_size ?? 0);
  const [rationale, setRationale] = useState("");

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "sampling.sample_sets" };
  else if (sets.isError || set.isError) {
    state = {
      kind: "error",
      retry: () => {
        void sets.refetch();
        void set.refetch();
      },
    };
  } else if (sets.isSuccess && list.length === 0) state = { kind: "empty" };
  else if (set.data === undefined) state = { kind: "loading" };

  const data = set.data;
  const approved = data?.status === "approved";
  const picker = (
    <Picker
      label={COPY.picker}
      variant="white"
      {...(current === undefined ? {} : { value: current })}
      options={list.map((s) => ({
        value: s.id,
        label: COPY.pickerRow(
          s.title,
          count(String(s.final_size)),
          count(String(s.population_count)),
          s.status === "approved" ? COPY.versions.approved : COPY.versions.draft,
        ),
      }))}
      onChange={(id) => {
        setChosen(id);
      }}
    />
  );
  const citations = (data?.parameters.citations ?? []).length;
  const generate = (
    <Button variant="primary" disabled={!approved}>
      {COPY.footer.generate(data?.items_total ?? 0, COPY.templates)}
    </Button>
  );
  return {
    title: COPY.title,
    well: true,
    state,
    empty: { title: COPY.states.empty },
    actions: (
      <>
        {data !== undefined && (
          <span
            data-aud11="version"
            className="rounded-full bg-nested px-[6px] text-meta text-ink-2"
          >
            {COPY.version(data.version_no)}
          </span>
        )}
        <PaneAction
          icon="pencil"
          label={COPY.actions.edit}
          onClick={() => {
            setEditing((e) => !e);
          }}
        />
        <PaneAction
          icon="check"
          label={COPY.actions.signOff}
          {...(data === undefined || options.onSignOff === undefined
            ? {}
            : {
                onClick: () => {
                  options.onSignOff?.(data.id, data.version_no);
                },
              })}
        />
        <PaneAction icon="file" label={COPY.actions.sourceDocs} />
      </>
    ),
    controls: list.length > 1 ? picker : undefined,
    footer:
      data === undefined ? undefined : (
        <div className="flex items-center gap-[8px]">
          {approved ? (
            generate
          ) : (
            <Tooltip content={COPY.footer.disabled}>
              <span tabIndex={0} data-aud11="generate-disabled">
                {generate}
              </span>
            </Tooltip>
          )}
          <span className="ml-auto flex gap-[6px]">
            {citations > 0 && (
              <Pill variant="neutral" size="sm">
                {COPY.footer.citations(citations)}
              </Pill>
            )}
          </span>
        </div>
      ),
    children:
      data === undefined ? null : (
        <Body
          set={data}
          editing={editing}
          size={editing && size === 0 ? data.parameters.final_size : size}
          onSize={setSize}
          rationale={rationale}
          onRationale={setRationale}
          onCancel={() => {
            setEditing(false);
            setRationale("");
          }}
        />
      ),
  };
}
