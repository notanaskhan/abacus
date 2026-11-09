import { returnRecordOptions, workspaceOptions } from "@abacus/api-client/query";
import { RecordCockpit, RecordHeader, Tabsbar, type ViewState } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX, ReactNode } from "react";
import { FORM_LABEL, stateOf } from "../TAX-02";
import { COPY as T02 } from "../TAX-02/copy";

// The review workspace frame (T-04-T12; T-04 §5; TAX-04 to TAX-08, TXI-01): new files over T-02's
// frame components, unchanged (`RecordCockpit`, `RecordHeader`, `Tabsbar`). The header reads the
// return's record (T-02's `GET /v1/tax-returns/{id}`); the tabs' counts, the Checkpoints chip and
// the Assistant chip read one workspace query (`GET /v1/tax/returns/{id}/workspace`): "Review n"
// at the viewer's level, "Issues n" open, "1 proposed" or "No changes needed". The routes hold
// the `tax.review_workspace` flag (routes/firm/tax-review.tsx); every section's body is its own
// screen's (T-04-T13 onward).

export type WorkspaceTab = "overview" | "intake" | "review" | "issues" | "activity";

export const WORKSPACE_COPY = {
  proposed: (n: number) => `${String(n)} proposed`,
  noChanges: "No changes needed",
} as const;

export interface WorkspaceFrameProps {
  returnId: string;
  tab: WorkspaceTab;
  onTab?: (tab: WorkspaceTab) => void;
  onCheckpoints?: () => void;
  onAssistant?: () => void;
  /** The section's canvas title (TAX-04 "Review", TAX-06 "Issues", …). */
  title: string;
  rail?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}

export function WorkspaceFrame(props: WorkspaceFrameProps): JSX.Element {
  const record = useQuery(returnRecordOptions({ path: { return_id: props.returnId } }));
  const summary = useQuery({
    ...workspaceOptions({ path: { return_id: props.returnId } }),
    retry: false,
  });
  const data = record.data;
  const ws = summary.data;
  const state: ViewState = record.isError
    ? {
        kind: "error",
        retry: () => {
          void record.refetch();
          void summary.refetch();
        },
      }
    : data === undefined
      ? { kind: "loading" }
      : { kind: "ready" };

  const proposed = ws?.checkpoints_proposed ?? 0;
  const header =
    data === undefined ? (
      <RecordHeader title="" checkpoints={false} sync={null} assistant={false} />
    ) : (
      (() => {
        const s = stateOf(data.row);
        return (
          <RecordHeader
            title={T02.formTitle(data.row.tax_year, FORM_LABEL[data.row.form])}
            context={data.row.client_name}
            state={s.label}
            {...(s.tone === null ? {} : { stateTone: s.tone })}
            checkpoints={ws !== undefined}
            checkpointsLabel={
              proposed > 0 ? WORKSPACE_COPY.proposed(proposed) : WORKSPACE_COPY.noChanges
            }
            checkpointsIcon={proposed > 0 ? "list" : "circle-check"}
            {...(props.onCheckpoints === undefined ? {} : { onCheckpoints: props.onCheckpoints })}
            sync={data.row.sync}
            assistant={ws !== undefined && ws.assistant !== "agents_off"}
            {...(props.onAssistant === undefined ? {} : { onAssistant: props.onAssistant })}
          />
        );
      })()
    );

  const count = (tab: WorkspaceTab): number | null =>
    ws === undefined
      ? null
      : tab === "review"
        ? ws.review_count
        : tab === "issues"
          ? ws.issues_open
          : null;
  const option = (key: WorkspaceTab) => {
    const n = count(key);
    return {
      label: T02.tabs[key],
      ...(n == null || n === 0 ? {} : { count: n }),
      ...(key === "issues" ? { bad: true } : {}),
    };
  };
  const keys: readonly WorkspaceTab[] = ["overview", "intake", "review", "issues", "activity"];
  const tabs = (
    <Tabsbar
      className="h-(--tabs-h-compact)"
      label={T02.tabs.label}
      options={keys.map(option)}
      active={T02.tabs[props.tab]}
      onChange={(label) => {
        const key = keys.find((k) => T02.tabs[k] === label);
        if (key !== undefined) props.onTab?.(key);
      }}
    />
  );
  return (
    <div data-screen="tax-workspace" data-tab={props.tab} className="flex min-h-0 flex-1 flex-col">
      <RecordCockpit
        header={header}
        tabs={tabs}
        rail={props.rail ?? null}
        canvas={{
          title: props.title,
          well: true,
          state,
          ...(props.actions === undefined ? {} : { actions: props.actions }),
          children: props.children ?? null,
        }}
      />
    </div>
  );
}
