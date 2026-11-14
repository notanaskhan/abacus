// SHL-23 live (I-02-T17; DEC-4938): the Today panel's views over the generated client: the day,
// the drill-in with Assign open items (SHL-17 prefilled, one at a time), History and a past brief
// (read only), and the ask thread on the Today session. HOME-05's dock and the `?ov=today`
// drawer both draw this.
import type { TodayVm } from "@abacus/api-client";
import { type JSX, useEffect, useState } from "react";
import {
  useAskToday,
  useAssignPrefills,
  usePastBrief,
  useTodayDrill,
  useTodayHistory,
} from "../../domain/today";
import { COPY } from "./copy";
import { AskThread, AssignSheet, TodayDrill, TodayHistory } from "./drill";
import { TodayPanel } from "./index";

type View =
  | { kind: "day" }
  | { kind: "drill"; workItemId: string; assign: boolean }
  | { kind: "history" }
  | { kind: "past"; briefId: string };

export interface TodayPaneLiveProps {
  vm: TodayVm | undefined;
  timeZone?: string;
  onOpen?: (href: string) => void;
  onRebuild?: () => void;
  onHighlight?: (refs: readonly string[] | null) => void;
}

export function TodayPaneLive({
  vm,
  timeZone,
  onOpen,
  onRebuild,
  onHighlight,
}: TodayPaneLiveProps): JSX.Element {
  const [view, setView] = useState<View>({ kind: "day" });
  const drill = useTodayDrill(view.kind === "drill" ? view.workItemId : null);
  const history = useTodayHistory(view.kind === "history");
  const past = usePastBrief(view.kind === "past" ? view.briefId : null);
  const ask = useAskToday(vm?.brief_id);
  const assign = useAssignPrefills(drill.data?.prefills ?? []);
  const wantsAssign = view.kind === "drill" && view.assign;
  const { start } = assign;
  useEffect(() => {
    if (wantsAssign && drill.data !== undefined) start();
  }, [wantsAssign, drill.data, start]);
  const back = () => {
    assign.cancel();
    onHighlight?.(null);
    setView({ kind: "day" });
  };
  if (view.kind === "drill" && drill.data !== undefined) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <TodayDrill
          drill={drill.data}
          onBack={back}
          onOpen={onOpen}
          onHighlight={onHighlight}
          onAssign={assign.start}
        />
        {assign.current !== null && assign.position !== null ? (
          <div className="flex-none p-[12px]">
            <AssignSheet
              prefill={assign.current}
              position={assign.position}
              of={(drill.data.prefills ?? []).length}
              creating={assign.creating}
              onCreate={(p) => {
                void assign.create(p);
              }}
              onSkip={assign.skip}
              onCancel={assign.cancel}
            />
          </div>
        ) : null}
      </div>
    );
  }
  if (view.kind === "history") {
    return (
      <TodayHistory
        page={history.data}
        onBack={back}
        onPick={(briefId) => {
          setView({ kind: "past", briefId });
        }}
      />
    );
  }
  if (view.kind === "past" && past.data !== undefined) {
    return (
      <TodayPanel
        vm={past.data}
        timeZone={timeZone}
        onOpen={onOpen}
        onHistory={() => {
          setView({ kind: "history" });
        }}
        readOnlyLine={COPY.pastBrief(past.data.brief_date)}
      />
    );
  }
  return (
    <TodayPanel
      vm={vm}
      timeZone={timeZone}
      onOpen={onOpen}
      onRebuild={onRebuild}
      onHighlight={onHighlight}
      onHistory={() => {
        setView({ kind: "history" });
      }}
      onDrill={(workItemId, wantAssign) => {
        setView({ kind: "drill", workItemId, assign: wantAssign });
      }}
      onAsk={(text) => {
        void ask.send(text);
      }}
      thread={<AskThread items={ask.items} pending={ask.pending} onOpen={onOpen} />}
    />
  );
}
