// K-03-T09 (TASK-8853; SH-1, C23; F-08 §4): the generated client's sheet in the kit's SheetVM, so
// SheetLayout renders what the server sends with nothing computed in the browser (ADR-050).
import type { SheetRowOut, SheetVmOut } from "@abacus/api-client";
import type { SheetGridRow, SheetVM } from "@abacus/ui";

export function toRow(r: SheetRowOut): SheetGridRow {
  return {
    key: r.key,
    sectionKey: r.section_key,
    locked: r.locked,
    version: r.version,
    cells: Object.fromEntries(
      Object.entries(r.cells).map(([k, c]) => [
        k,
        {
          value: c.value,
          state: c.state,
          ...(c.raw == null ? {} : { raw: c.raw }),
          ...(c.at == null ? {} : { at: c.at }),
          ...(c.was == null ? {} : { was: c.was }),
          ...(c.exception ? { exception: true } : {}),
        },
      ]),
    ),
  };
}

export function toSheetVM(s: SheetVmOut, rows: readonly SheetRowOut[]): SheetVM {
  return {
    sheetId: s.sheet_id,
    workItemId: s.work_item_id,
    title: s.title,
    columns: s.columns.map((c) => ({
      key: c.key,
      type: c.type,
      label: c.label,
      width: c.width,
      ...(c.frozen ? { frozen: true } : {}),
      ...(c.agent_name == null
        ? {}
        : {
            agent: {
              name: c.agent_name,
              ...(c.agent_unavailable == null ? {} : { unavailable: c.agent_unavailable }),
            },
          }),
      ...(c.options && c.options.length ? { options: c.options } : {}),
    })),
    sections: s.sections.map((x) => ({
      key: x.key,
      title: x.title,
      count: x.count,
      ...(x.total == null ? {} : { total: x.total }),
      ...(x.sub ? { sub: true } : {}),
    })),
    rows: rows.map(toRow),
    status: {
      rows: s.status.rows,
      exceptions: s.status.exceptions,
      view: s.status.view,
      ...(s.status.agent_running ? { agentRunning: true } : {}),
      ...(s.status.agent_summary == null ? {} : { agentSummary: s.status.agent_summary }),
    },
    signedOff: s.signed_off ?? false,
    allowedActions: s.allowed_actions ?? [],
  };
}
