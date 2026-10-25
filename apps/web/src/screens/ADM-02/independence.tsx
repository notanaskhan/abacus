// ADM-02g (DF-07, DEC-91, DEC-352): the annual independence confirmations for the year. Each seat
// holder's status (Confirmed with its date · Not yet · Declined with a note) in the T1 table
// grammar under a counts line that foots to the seat holders (G-01 AC6.3). Names come from the
// firm's member list; the rows carry only ids. Nobody confirms here: a member confirms for
// themself from the profile drawer (G-01-T13), and agents and the system never can.

import type { AnnualIndependenceOut, FirmMemberOut } from "@abacus/api-client";
import { RegistryStatus, SkeletonRows } from "@abacus/ui";
import type { JSX } from "react";
import { COPY } from "./copy";
import { dayOf } from "./model";

export interface IndependenceProps {
  data: AnnualIndependenceOut | undefined;
  members: readonly FirmMemberOut[];
  when: { now: Date; tz: string };
}

export function Independence({ data, members, when }: IndependenceProps): JSX.Element {
  if (data === undefined) return <SkeletonRows type="table" />;
  const names = new Map(members.map((m) => [m.user_id, m.display_name]));
  const c = data.counts;
  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between px-[16px] py-[12px]">
        <h3 className="text-section">{COPY.independence.title(data.year)}</h3>
        <span className="text-body text-ink-3">
          {COPY.independence.counts(c.confirmed ?? 0, c.not_yet ?? 0, c.declined ?? 0)}
        </span>
      </div>
      <table
        aria-label={COPY.independence.table}
        className="w-full border-collapse text-left text-body"
      >
        <thead>
          <tr>
            {[
              COPY.independence.person,
              COPY.independence.status,
              COPY.independence.decided,
              COPY.independence.note,
            ].map((label, i) => (
              <th
                key={label}
                scope="col"
                className={`h-[30px] bg-band-hd px-[8px] text-th font-normal text-ink-2 hairline-b ${i === 0 ? "pl-[16px]" : ""}`}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row) => (
            <tr key={row.user_id} data-person={names.get(row.user_id) ?? ""}>
              <td className="h-[44px] py-[5px] pr-[8px] pl-[16px] font-medium hairline-b">
                {names.get(row.user_id) ?? COPY.none}
              </td>
              <td className="px-[8px] py-[5px] hairline-b">
                <RegistryStatus object="annual_independence" code={row.status} />
              </td>
              <td className="px-[8px] py-[5px] text-dense text-ink-2 hairline-b">
                {row.decided_at == null ? COPY.none : dayOf(row.decided_at, when)}
              </td>
              <td className="px-[8px] py-[5px] text-dense text-ink-2 hairline-b">
                {row.note ?? ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
