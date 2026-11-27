// SHT-02 · Column and field configurator (K-03-T23; TASK-9029; DEC-6034): the O2 480 drawer over
// SHT-01 at `?ov=column:new[:<afterKey>]` or `?ov=column:<columnId>`, with T12's Fieldset grammar
// and no boxed inputs but the two editable values. It adds or changes one typed column and shows
// what depends on it: the 11 types of §5.2 in order, a date range shown as a month, Required, the
// four ADR-031 levels (Restricted by default for a column of client data; a lower level needs a
// reason), and the server's "Used in" (views, rules, agent columns). Changing a used column's type
// warns before it converts (d); deleting a used column is refused with the reason (e). Only a
// person with `sheet.configure` saves; anyone else reads it and may suggest the change to the
// configurer through an SHL-18 comment with the @mention prefilled (f). `mode="template"` is
// KNW-06's: the same drawer over a firm template's sheet definition (its save is K-03-T52's).
// The columns service is K-03-T24: until then the writes answer 501 and the screen says so.
import type { ColumnUsageOut, SheetColumnIn, SheetColumnOut } from "@abacus/api-client";
import {
  sheetColumnCreateMutation,
  sheetColumnPatchMutation,
  sheetColumnUsageOptions,
  sheetOptions,
  sheetQueryKey,
} from "@abacus/api-client/query";
import {
  Button,
  Dialog,
  Drawer,
  Fieldset,
  Icon,
  type IconName,
  Picker,
  Skeleton,
  Tag,
  Toggle,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { type JSX, type ReactNode, useState } from "react";
import { useCan } from "../../app-core/can";
import { useOpenOverlay } from "../../app-core/open";
import type { OverlayRenderProps } from "../../app-core/overlays";
import { useSession } from "../../app-core/session";
import { LiveCommentThread } from "../../domain/collaboration";
import { ov } from "../../routes/to";
import { COPY as C } from "./copy";

type ColumnType = SheetColumnIn["type"];
type Level = NonNullable<SheetColumnIn["classification"]>;

/** Lucide glyphs of the 11 types (SHT-02 spec, COMPONENTS). */
const GLYPH: Record<ColumnType, IconName> = {
  text: "type",
  number: "hash",
  currency: "circle-dollar-sign",
  date: "calendar",
  single_select: "list",
  person: "user",
  linked_evidence: "paperclip",
  linked_request: "inbox",
  linked_risk: "shield-alert",
  sign_off: "signature",
  agent: "atom",
};

/** Types whose values are client data (Restricted by default; a lower level needs a reason). */
const CLIENT_DATA: ReadonlySet<ColumnType> = new Set<ColumnType>([
  "text",
  "number",
  "currency",
  "date",
  "single_select",
  "linked_evidence",
  "linked_request",
  "linked_risk",
  "agent",
]);

interface Draft {
  label: string;
  description: string;
  type: ColumnType;
  dateRange: boolean;
  required: boolean;
  classification: Level;
  reason: string;
}

function draftOf(column: SheetColumnOut | undefined): Draft {
  return {
    label: column?.label ?? "",
    description: column?.description ?? "",
    type: column?.type ?? "date",
    dateRange: column?.date_range ?? true,
    required: column?.required ?? true,
    classification: column?.classification ?? "restricted",
    reason: "",
  };
}

/** A new column's key from its name: "Service period" is `service_period`. */
function keyOf(label: string): string {
  const key = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/gu, "_")
    .replace(/^_+|_+$/gu, "");
  return /^[a-z]/u.test(key) ? key.slice(0, 60) : `column_${key}`.slice(0, 60);
}

const same = (a: Draft, b: Draft): boolean => JSON.stringify(a) === JSON.stringify(b);

function Row({
  k,
  children,
  indent = false,
  sub,
}: {
  k: string;
  children: ReactNode;
  indent?: boolean;
  sub?: string;
}): JSX.Element {
  return (
    <div
      className={`flex min-h-[34px] items-center justify-between gap-[12px] py-[4px] pr-[12px] hairline-b last:shadow-none ${indent ? "pl-[24px]" : "pl-[12px]"}`}
    >
      <span className="flex flex-col">
        <span className="text-[13px] text-ink-2">{k}</span>
        {sub === undefined ? null : <span className="text-[11.5px] text-ink-3">{sub}</span>}
      </span>
      <span className="flex items-center gap-[6px] text-right text-[13px] font-medium">
        {children}
      </span>
    </div>
  );
}

function Help({ children }: { children: ReactNode }): JSX.Element {
  return (
    <p className="px-[12px] pt-[8px] pb-[10px] text-[11.5px] leading-[1.45] text-ink-3">
      {children}
    </p>
  );
}

function Value({
  label,
  value,
  lines = 1,
  readOnly,
  onChange,
}: {
  label: string;
  value: string;
  lines?: number;
  readOnly: boolean;
  onChange: (v: string) => void;
}): JSX.Element {
  return (
    <textarea
      aria-label={label}
      rows={lines}
      value={value}
      readOnly={readOnly}
      onChange={(e) => {
        onChange(e.target.value.replace(/\n/gu, lines === 1 ? "" : "\n"));
      }}
      className="w-[240px] resize-none rounded-[6px] bg-nested px-[8px] py-[4px] text-right text-[13px] font-medium outline-none focus-visible:shadow-focus"
    />
  );
}

export interface ColumnDrawerProps {
  sheetId: string;
  /** `new`, or the column being edited. */
  columnId: string;
  /** New columns go after this one (the header menu's column), else last. */
  afterKey?: string | undefined;
  mode?: "sheet" | "template";
  onClose: () => void;
  /** Open on mount, as an artboard opens: the blocked-delete dialog (e). */
  initialDelete?: boolean;
  /** As an artboard opens: the type already changed to this one (d). */
  initialType?: ColumnType;
}

export function ColumnDrawer({
  sheetId,
  columnId,
  afterKey,
  mode = "sheet",
  onClose,
  initialDelete = false,
  initialType,
}: ColumnDrawerProps): JSX.Element {
  const queries = useQueryClient();
  const openOverlay = useOpenOverlay();
  const viewerId = useSession().user?.id ?? "";
  const manager = useCan("sheet.configure");
  const path = { sheet_id: sheetId };
  const sheet = useQuery(sheetOptions({ path }));
  const isNew = columnId === "new";
  const column = sheet.data?.columns.find((c) => c.column_id === columnId);
  const usage = useQuery({
    ...sheetColumnUsageOptions({ path: { sheet_id: sheetId, column_id: columnId } }),
    enabled: !isNew,
  });
  const [saved, setSaved] = useState<Draft | null>(null);
  const [draft, setDraftState] = useState<Draft | null>(null);
  const [pendingType, setPendingType] = useState<ColumnType | null>(initialType ?? null);
  const [blocked, setBlocked] = useState(initialDelete);
  const [suggesting, setSuggesting] = useState(false);
  const base = saved ?? draftOf(isNew ? undefined : column);
  const current = draft ?? base;
  const set = (patch: Partial<Draft>): void => {
    setDraftState({ ...current, ...patch });
  };
  const after =
    sheet.data?.columns.find((c) => c.key === (afterKey ?? column?.key ?? "")) ??
    sheet.data?.columns.at(-1);
  const create = useMutation({ ...sheetColumnCreateMutation() });
  const patch = useMutation({ ...sheetColumnPatchMutation() });
  const u: ColumnUsageOut = usage.data ?? { filled_rows: 0, views: 0, in_use: false };
  const used = {
    views: u.views,
    viewNames: u.view_names ?? [],
    rules: u.rules ?? 0,
    agentColumns: u.agent_columns ?? [],
  };
  const label = current.label.trim() === "" ? (column?.label ?? "") : current.label.trim();
  const lowered = CLIENT_DATA.has(current.type) && current.classification !== "restricted";
  const changed = !same(current, base);
  const valid = current.label.trim() !== "" && (!lowered || current.reason.trim() !== "");
  const readOnly = !manager;

  const body: SheetColumnIn = {
    key: column?.key ?? keyOf(current.label),
    type: current.type,
    label: current.label.trim(),
    description: current.description.trim() === "" ? null : current.description.trim(),
    date_range: current.type === "date" && current.dateRange,
    display: current.type === "date" && current.dateRange ? "month" : null,
    required: current.required,
    validation: current.type === "date" && current.dateRange ? "end_on_or_after_start" : null,
    classification: current.classification,
    classification_reason: lowered ? current.reason.trim() : null,
    ...(after === undefined ? {} : { after_key: after.key }),
  };
  const save = async (): Promise<void> => {
    try {
      if (isNew) await create.mutateAsync({ path, body });
      else await patch.mutateAsync({ path: { sheet_id: sheetId, column_id: columnId }, body });
      toast.show({ kind: "info", text: (isNew ? C.added : C.saved)(body.label) });
      setSaved(current);
      setDraftState(null);
      await queries.invalidateQueries({ queryKey: sheetQueryKey({ path }) });
      if (isNew) onClose();
    } catch {
      toast.show({ kind: "error", text: C.failed });
    }
  };
  const pickType = (value: string): void => {
    const next = value as ColumnType;
    if (next === "agent") {
      // Picking "Agent column" closes this drawer and opens SHT-04 (K-03-T31).
      onClose();
      openOverlay(ov.SHT04(isNew ? "new" : columnId));
      return;
    }
    if (!isNew && next !== current.type && u.filled_rows > 0) {
      setPendingType(next); // d: warn before converting values
      return;
    }
    set({ type: next });
  };
  const typeLabel = (t: ColumnType): string => C.types.find((x) => x.value === t)?.label ?? t;

  const footer = readOnly ? undefined : (
    <div className="flex items-center justify-between gap-[8px]">
      <span className="flex gap-[8px]">
        <Button variant="ghost" size="sm" onClick={onClose}>
          {C.cancel}
        </Button>
        {isNew || mode === "template" ? null : (
          <Button
            variant="ghost"
            size="sm"
            className="text-red-ink"
            onClick={() => {
              if (u.in_use) setBlocked(true);
            }}
          >
            {C.deleteColumn}
          </Button>
        )}
      </span>
      <Button
        variant="primary"
        size="sm"
        disabled={!changed || !valid || create.isPending || patch.isPending}
        onClick={() => void save()}
      >
        {isNew ? C.add : C.save}
      </Button>
    </div>
  );

  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={isNew ? C.addTitle : C.editTitle(column?.label ?? "")}
      description={sheet.data?.title ?? ""}
      width={480}
      dirty={changed}
      {...(footer === undefined ? {} : { footer })}
    >
      {sheet.isError ? (
        <p role="alert" className="text-[13px]">
          {C.loadFailed}
        </p>
      ) : sheet.data === undefined ? (
        <Skeleton className="h-[500px]" />
      ) : (
        <div className="flex flex-col gap-[12px]" data-screen="SHT-02">
          {readOnly ? (
            <div
              role="status"
              className="flex min-h-[34px] items-center justify-between gap-[8px] rounded-nested bg-nested px-[12px] text-[12.5px]"
              data-sht02="read-only"
            >
              <span>{C.readOnly}</span>
              {sheet.data.configurer ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setSuggesting(true);
                  }}
                >
                  {C.suggest(sheet.data.configurer)}
                </Button>
              ) : null}
            </div>
          ) : null}
          {suggesting && sheet.data.configurer ? (
            <LiveCommentThread
              variant="drawer"
              anchor={{ anchor_kind: "sheet", anchor_id: sheetId }}
              anchorLabel={sheet.data.title}
              engagementId={sheet.data.engagement_id ?? ""}
              engagementLabel={sheet.data.title}
              viewerId={viewerId}
              initialDraft={`@${sheet.data.configurer} `}
            />
          ) : null}
          <Fieldset title={C.sections.column} flush>
            <Row k={C.keys.name}>
              <Value
                label={C.keys.name}
                value={current.label}
                readOnly={readOnly}
                onChange={(v) => {
                  set({ label: v });
                }}
              />
            </Row>
            <Row k={C.keys.description}>
              <Value
                label={C.keys.description}
                value={current.description}
                lines={2}
                readOnly={readOnly}
                onChange={(v) => {
                  set({ description: v });
                }}
              />
            </Row>
            {after === undefined ? null : <Row k={C.keys.position}>{C.after(after.label)}</Row>}
          </Fieldset>
          <Fieldset title={C.sections.type} flush>
            <Row k={C.keys.type}>
              <Icon name={GLYPH[current.type]} size={12} className="text-ink-3" />
              <Picker
                label={C.keys.type}
                variant="fill"
                menuWidth={280}
                disabled={readOnly}
                options={C.types.map((t) => ({
                  value: t.value,
                  label: t.label,
                  ...(t.hint === undefined ? {} : { hint: t.hint }),
                }))}
                value={current.type}
                onChange={pickType}
              />
            </Row>
            {pendingType === null ? null : (
              <div
                role="alert"
                data-sht02="type-warning"
                className="mx-[12px] my-[8px] flex flex-col gap-[8px] rounded-nested bg-amber-tint px-[10px] py-[8px] text-[12px] text-amber-ink"
              >
                <span className="flex gap-[6px]">
                  <Icon name="triangle-alert" size={13} className="mt-[1px] flex-none" />
                  {C.typeWarning(
                    typeLabel(current.type),
                    typeLabel(pendingType),
                    u.filled_rows,
                    used,
                    column?.label ?? label,
                  )}
                </span>
                <span className="flex justify-end gap-[6px]">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setPendingType(null);
                    }}
                  >
                    {C.keepType(typeLabel(current.type))}
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      set({ type: pendingType });
                      setPendingType(null);
                    }}
                  >
                    {C.changeType}
                  </Button>
                </span>
              </div>
            )}
            {current.type === "date" ? (
              <>
                <Row k={C.keys.range} indent>
                  <span className="text-[12px] font-normal text-ink-3">{C.rangeHint}</span>
                  <Toggle
                    label={C.keys.range}
                    checked={current.dateRange}
                    disabled={readOnly}
                    onChange={(on) => {
                      set({ dateRange: on });
                    }}
                  />
                </Row>
                <Row k={C.keys.display} indent>
                  {current.dateRange ? C.display.month : C.display.date}
                </Row>
              </>
            ) : null}
          </Fieldset>
          <Fieldset title={C.sections.rules} flush>
            <Row k={C.keys.required} sub={C.requiredHint}>
              <Toggle
                label={C.keys.required}
                checked={current.required}
                disabled={readOnly}
                onChange={(on) => {
                  set({ required: on });
                }}
              />
            </Row>
            <Row k={C.keys.defaultValue}>{C.defaultEmpty}</Row>
            {current.type === "date" && current.dateRange ? (
              <Row k={C.keys.validation}>{C.validation.end_on_or_after_start}</Row>
            ) : null}
            <Row k={C.keys.visible}>
              {/* An internal workpaper never shows a column to the client. */}
              <Toggle label={C.keys.visible} checked={false} disabled />
            </Row>
            <Help>{C.visibleHelp}</Help>
          </Fieldset>
          <Fieldset title={C.sections.data} flush>
            <Row k={C.keys.classification}>
              <Picker
                label={C.keys.classification}
                variant="fill"
                menuWidth={280}
                disabled={readOnly}
                options={C.levels.map((l) => ({
                  value: l.value,
                  label: l.label,
                  ...(l.hint === undefined ? {} : { hint: l.hint }),
                }))}
                value={current.classification}
                onChange={(v) => {
                  set({ classification: v as Level });
                }}
              />
              <Tag>{C.requiredTag}</Tag>
            </Row>
            <Help>{C.classificationHelp}</Help>
            {lowered ? (
              <Row k={C.reasonLabel}>
                <Value
                  label={C.reasonLabel}
                  value={current.reason}
                  lines={2}
                  readOnly={readOnly}
                  onChange={(v) => {
                    set({ reason: v });
                  }}
                />
              </Row>
            ) : null}
            <Row k={C.keys.usedIn}>
              <span className="flex flex-col items-end">
                <span className="text-[12.5px] font-normal text-ink-3" data-sht02="used-in">
                  {C.usedIn(used, column?.label ?? label)}
                </span>
                {u.filled_rows > 0 ? (
                  <span className="text-[12px] font-normal text-ink-3">
                    {C.filled(u.filled_rows)}
                  </span>
                ) : null}
              </span>
            </Row>
          </Fieldset>
          <p className="flex gap-[6px] text-[12px] leading-[1.5] text-ink-2">
            <Icon name="info" size={13} className="mt-[2px] flex-none" />
            {mode === "template" ? C.templateNote : C.note}
          </p>
        </div>
      )}
      <Dialog
        open={blocked}
        onOpenChange={setBlocked}
        title={C.blockedTitle(column?.label ?? label)}
        size="lg"
        action={
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              setBlocked(false);
            }}
          >
            {C.close}
          </Button>
        }
      >
        <p className="text-[12.5px] leading-[1.55]">
          {C.blockedBody(used, column?.label ?? label)}
        </p>
        {used.agentColumns.map((name) => {
          const agent = sheet.data?.columns.find((c) => c.type === "agent" && c.label === name);
          return (
            <Button
              key={name}
              variant="secondary"
              size="sm"
              className="mt-[12px]"
              onClick={() => {
                setBlocked(false);
                onClose();
                if (agent !== undefined) openOverlay(ov.SHT04(agent.column_id));
              }}
            >
              {C.openAgent(name)}
            </Button>
          );
        })}
      </Dialog>
    </Drawer>
  );
}

/** The `?ov=column:new[:<afterKey>]` / `?ov=column:<columnId>` layer over SHT-01. */
export function ColumnLayer({ ref, close }: OverlayRenderProps): JSX.Element | null {
  const params: { sheetId?: string } = useParams({ strict: false });
  const [columnId, afterKey] = ref.args;
  if (columnId === undefined || params.sheetId === undefined) return null;
  return (
    <ColumnDrawer
      sheetId={params.sheetId}
      columnId={columnId}
      afterKey={afterKey}
      onClose={close}
    />
  );
}
