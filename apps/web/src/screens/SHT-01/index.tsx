// SHT-01 · BH-FS-430 Search for Unrecorded Liabilities — sheet (K-03-T16; TASK-8932; SH-1, C23;
// handoff SHT-01 b, c, a, f; DEC-5934) on T18 SheetLayout inside the audit cockpit with the rail
// hidden, at /audits/$auditId/sheets/$sheetId. The audit bar (All Audits chip, the engagement and
// the sheet's methodology chip), the 44 sheet toolbar (views, filter, columns, search, Sign-offs,
// Agents, Comments), strata bands with their totals and the status bar are the server's (`GET
// /v1/sheets/{id}`, `…/rows`) through the SheetVM adapter: the browser formats and never adds.
// a, b, c and f are this row's: the agent column joins with K-03's agent row, so it is not drawn
// here. Locked rows (f) refuse edits with the kit's final tooltip; locks come from sign-off state
// only (ADR P-07). "Sign-offs" opens SHL-12 (`?ov=signoff`) for the selected rows; nothing here
// signs. No column letters, row numbers or zebra rows (the kit draws none).
import type { SheetRowOut } from "@abacus/api-client";
import {
  sheetOptions,
  sheetQueryKey,
  sheetRowPatchMutation,
  sheetRowsOptions,
  sheetRowsQueryKey,
} from "@abacus/api-client/query";
import { Button, Icon, SheetLayout, type SheetLayoutProps, Skeleton, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, useMemo, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { useSession } from "../../app-core/session";
import { toSheetVM } from "../../domain/sheets";
import { ov, to } from "../../routes/to";
import { COPY as C } from "./copy";

export interface SHT01Props {
  auditId: string;
  sheetId: string;
}

export function SHT01({ auditId, sheetId }: SHT01Props): JSX.Element {
  const queries = useQueryClient();
  const openOverlay = useOpenOverlay();
  const name = useSession().user?.displayName ?? "";
  const path = { sheet_id: sheetId };
  const sheet = useQuery(sheetOptions({ path }));
  const rows = useQuery(sheetRowsOptions({ path }));
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const patch = useMutation({
    ...sheetRowPatchMutation(),
    onSettled: async () => {
      await queries.invalidateQueries({ queryKey: sheetRowsQueryKey({ path }) });
      await queries.invalidateQueries({ queryKey: sheetQueryKey({ path }) });
    },
  });
  const items: readonly SheetRowOut[] = rows.data?.items ?? [];
  const vm = useMemo(
    () => (sheet.data === undefined ? undefined : toSheetVM(sheet.data, items)),
    [sheet.data, items],
  );

  if (sheet.isError || rows.isError) {
    return (
      <div
        data-screen="SHT-01"
        role="alert"
        className="flex flex-col items-start gap-[8px] p-[24px]"
      >
        <p className="text-[13px]">{C.failed}</p>
        <Button variant="secondary" size="sm" onClick={() => void sheet.refetch()}>
          {C.retry}
        </Button>
      </div>
    );
  }
  if (vm === undefined || rows.isPending) {
    return (
      <div data-screen="SHT-01" aria-busy="true" className="flex flex-col gap-[10px] p-[12px]">
        <Skeleton className="h-[59px] w-full" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }
  // The agent column is K-03's agent row (SHT-01 d, e); this row draws the sheet without it.
  const columns = vm.columns.filter((c) => c.type !== "agent");
  const shown = vm.rows.filter((r) =>
    search.trim() === ""
      ? true
      : Object.values(r.cells).some((cell) =>
          cell.value.toLowerCase().includes(search.trim().toLowerCase()),
        ),
  );
  const openSignOff = (keys: readonly string[], level?: "P" | "R"): void => {
    if (keys.length === 0) {
      toast.show({ text: C.selectRows });
      return;
    }
    openOverlay(ov.SHL12("sheet_row", keys.join(","), level));
  };
  const layout: SheetLayoutProps = {
    variant: "full",
    view: vm.rows.length === 0 ? "empty" : "ready",
    toolbar: {
      view: C.defaultView,
      filters: 0,
      search,
      onSearch: setSearch,
      onSignOffs: () => {
        openSignOff([...selected]);
      },
    },
    grid: {
      label: vm.title,
      columns,
      sections: vm.sections,
      rows: shown,
      status: vm.status,
      viewer: { kind: "human", name },
      height: 600,
      selected,
      onOpenRow: (key) => {
        openOverlay(ov.SHT01Row(key));
      },
      onSelect: (key, on) => {
        setSelected((s) => {
          const next = new Set(s);
          if (on) next.add(key);
          else next.delete(key);
          return next;
        });
      },
      onCellEdit: async (edit) => {
        const row = items.find((r) => r.key === edit.rowKey);
        if (row === undefined || row.locked) return;
        await patch.mutateAsync({
          path: { sheet_id: sheetId, row_id: row.row_id },
          body: { cells: { [edit.colKey]: edit.value }, version: edit.version ?? row.version },
        });
      },
    },
    onOpenSignOff: (keys, level) => {
      openSignOff(keys, level);
    },
  };
  return (
    <div data-screen="SHT-01" className="flex min-h-0 flex-1 flex-col">
      <div
        className="relative flex h-[59px] flex-none items-center px-[12px]"
        data-sht01="audit-bar"
      >
        <Link
          {...to.AUD02({ auditId })}
          className="z-10 flex h-[29px] items-center gap-[4px] rounded-full bg-card px-[10px] text-[13px] shadow-e1"
        >
          <Icon name="chevron-left" size={14} />
          {C.allAudits}
        </Link>
        <h1 className="absolute inset-x-0 flex items-center justify-center gap-[8px] text-[15px]">
          <span className="font-medium">{vm.title}</span>
        </h1>
      </div>
      <div className="flex min-h-0 flex-1 flex-col px-[12px] pb-[12px]">
        <SheetLayout {...layout} />
      </div>
    </div>
  );
}
