// AUD-14 live (A-08-T32; TASK-8545; DEC-5530): the confirmations log, the summary's coverage line
// and the open row's drawer on `GET /v1/work-items/{id}/confirmations`, `…/confirmations/summary`
// and `GET /v1/confirmations/{id}`. Every figure is the API's (book, confirmed and code's
// difference; coverage); the words are the handoff's (copy.ts) with the API's dates and people.
// A refused or failed read is the C-20 frame; nothing here is client-visible.
import type { ConfirmationRowOut } from "@abacus/api-client";
import {
  confirmationSummaryOptions,
  getConfirmationOptions,
  listConfirmationsOptions,
} from "@abacus/api-client/query";
import { ErrorState, Skeleton, date } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenOverlay } from "../../app-core/open";
import { ov } from "../../routes/to";
import type { ConfirmationLogRow } from "../kit-a08-data";
import { AUD14_COPY as C } from "./copy";
import { ConfirmationsWorkspace } from "./index";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter((w) => w !== "")
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/** One API row as the log draws it. */
export function logRowOf(r: ConfirmationRowOut, now: Date): ConfirmationLogRow {
  const on = (at: string | null | undefined): string => (at == null ? "" : date(at, { now }));
  const check = r.address_check ?? null;
  const awaiting = r.status === "sent" && r.responded_at === null;
  const subLine =
    awaiting && r.second_request_at !== null
      ? C.secondRequestOn(on(r.second_request_at))
      : awaiting && r.viewed_at !== null
        ? C.viewedOn(on(r.viewed_at))
        : undefined;
  return {
    number: r.number,
    item: C.items[r.type],
    respondent: r.respondent_org,
    address:
      check === null
        ? ""
        : C.addressCheck(check.method, initials(check.verified_by_name), on(check.verified_on)),
    channel: C.channels[r.channel],
    sent: on(r.sent_at),
    response: r.responded_at !== null ? on(r.responded_at) : awaiting ? C.noResponse : "",
    book: r.book_total,
    confirmed: r.confirmed_total ?? null,
    difference: r.difference ?? null,
    status: r.status,
    ...(subLine === undefined ? {} : { subLine }),
  };
}

export function AUD14Live({ workItemId }: { workItemId: string }): JSX.Element {
  const now = useNow();
  const path = { path: { work_item_id: workItemId } };
  const log = useQuery(listConfirmationsOptions(path));
  const summary = useQuery(confirmationSummaryOptions(path));
  const openOverlay = useOpenOverlay();
  const [selected, setSelected] = useState<string | null>(null);
  const openId = log.data?.items.find((r) => r.number === selected)?.id;
  const detail = useQuery({
    ...getConfirmationOptions({ path: { confirmation_id: openId ?? "" } }),
    enabled: openId !== undefined,
  });
  if (log.isError || summary.isError) {
    return (
      <ErrorState
        onRetry={() => {
          void log.refetch();
          void summary.refetch();
        }}
      />
    );
  }
  if (log.data === undefined || summary.data === undefined) {
    return <Skeleton className="h-[480px]" />;
  }
  return (
    <div data-live="true">
      <ConfirmationsWorkspace
        data={{
          rows: log.data.items.map((r) => logRowOf(r, now)),
          coverage: summary.data.coverage,
          detail: openId === undefined ? undefined : detail.data,
          selected,
          onSelect: setSelected,
          onBook: (number) => {
            const row = log.data.items.find((r) => r.number === number);
            if (row !== undefined) openOverlay(ov.SHL09("confirmation", row.id, "book_total"));
          },
        }}
      />
    </div>
  );
}
