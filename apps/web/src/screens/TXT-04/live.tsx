import {
  estateComputationOptions,
  estateDeductionsOptions,
  estateGiftsOptions,
  estateInventoryOptions,
} from "@abacus/api-client/query";
import { ErrorState, Segmented, Skeleton, count, useFormat } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";

// TXT-04 live (S47, TASK-8353): the estate workpapers on GET /v1/tax/returns/{id}/estate/*,
// every figure the API's (code's engine; tables carry no dollar sign; the state card never shows
// a figure while it is pending). The section labels are the handoff's TXT-04.

type Section = "inventory" | "deductions" | "computation" | "gifts";
const SECTIONS: readonly { key: Section; label: string }[] = [
  { key: "inventory", label: "Inventory" },
  { key: "deductions", label: "Deductions" },
  { key: "computation", label: "Computation" },
  { key: "gifts", label: "Gift history" },
];
const money = (v: string | null | undefined): string =>
  v === null || v === undefined ? "—" : count(v);

export interface Txt04LiveProps {
  returnId: string;
  initial?: Section;
}

export function TXT04({ returnId, initial = "inventory" }: Txt04LiveProps): JSX.Element {
  const [section, setSection] = useState<Section>(initial);
  return (
    <div data-screen="TXT-04" data-live data-section={section} className="flex flex-col bg-shell">
      <Segmented
        label="Estate workpapers"
        options={SECTIONS.map((s) => s.label)}
        active={SECTIONS.find((s) => s.key === section)?.label ?? "Inventory"}
        onChange={(label) => {
          setSection(SECTIONS.find((s) => s.label === label)?.key ?? "inventory");
        }}
      />
      {section === "inventory" && <Inventory returnId={returnId} />}
      {section === "deductions" && <Deductions returnId={returnId} />}
      {section === "computation" && <Computation returnId={returnId} />}
      {section === "gifts" && <Gifts returnId={returnId} />}
    </div>
  );
}

function Pending({ error, retry }: { error: boolean; retry: () => void }): JSX.Element {
  return error ? <ErrorState onRetry={retry} /> : <Skeleton className="h-[280px]" />;
}

function Inventory({ returnId }: { returnId: string }): JSX.Element {
  const q = useQuery(estateInventoryOptions({ path: { return_id: returnId } }));
  if (q.data === undefined) return <Pending error={q.isError} retry={() => void q.refetch()} />;
  return (
    <table aria-label="Inventory">
      <thead>
        <tr>
          <th>Schedule</th>
          <th>Asset</th>
          <th>Date-of-death value</th>
          <th>Alternate valuation</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {q.data.assets.map((a) => (
          <tr key={a.id} data-status={a.status}>
            <td>{a.schedule}</td>
            <td>{a.description}</td>
            <td>{money(a.dod_value)}</td>
            <td>{money(a.avd_value)}</td>
            <td>{a.status}</td>
          </tr>
        ))}
        <tr>
          <td>Total</td>
          <td />
          <td>{money(q.data.totals.dod_value)}</td>
          <td>{money(q.data.totals.avd_value)}</td>
          <td />
        </tr>
      </tbody>
    </table>
  );
}

function Deductions({ returnId }: { returnId: string }): JSX.Element {
  const q = useQuery(estateDeductionsOptions({ path: { return_id: returnId } }));
  if (q.data === undefined) return <Pending error={q.isError} retry={() => void q.refetch()} />;
  return (
    <table aria-label="Deductions">
      <thead>
        <tr>
          <th>Schedule</th>
          <th>Deduction</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        {q.data.deductions.map((d) => (
          <tr key={d.id} data-estimated={d.estimated}>
            <td>{d.schedule}</td>
            <td>{d.description}</td>
            <td>{money(d.amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Computation({ returnId }: { returnId: string }): JSX.Element {
  const q = useQuery(estateComputationOptions({ path: { return_id: returnId } }));
  if (q.data === undefined) return <Pending error={q.isError} retry={() => void q.refetch()} />;
  const data = q.data;
  return (
    <section aria-label="Computation">
      {data.filing_banner ? <p role="note">{data.filing_banner}</p> : null}
      <dl>
        {data.lines.map((l) => (
          <div key={l.key} className="flex justify-between">
            <dt>{l.label}</dt>
            <dd>{money(l.value)}</dd>
          </div>
        ))}
      </dl>
      <p data-state-card={data.state_card.jurisdiction}>
        {data.state_card.jurisdiction} estate tax · {data.state_card.status}
      </p>
    </section>
  );
}

function Gifts({ returnId }: { returnId: string }): JSX.Element {
  const q = useQuery(estateGiftsOptions({ path: { return_id: returnId } }));
  const fmt = useFormat();
  if (q.data === undefined) return <Pending error={q.isError} retry={() => void q.refetch()} />;
  return (
    <table aria-label="Gift history">
      <thead>
        <tr>
          <th>Year</th>
          <th>Donee</th>
          <th>Asset</th>
          <th>Gift</th>
          <th>Annual exclusion</th>
          <th>Taxable gift</th>
          <th>Filed</th>
        </tr>
      </thead>
      <tbody>
        {q.data.gifts.map((g) => (
          <tr key={g.id}>
            <td>{g.year}</td>
            <td>{g.donee_name}</td>
            <td>{g.asset}</td>
            <td>{money(g.gift_amount)}</td>
            <td>{money(g.annual_exclusion)}</td>
            <td>{money(g.taxable_gift)}</td>
            <td>{g.filed_on ? fmt.date(g.filed_on) : "—"}</td>
          </tr>
        ))}
        <tr data-tie={q.data.tie}>
          <td>Adjusted taxable gifts</td>
          <td colSpan={4} />
          <td>{money(q.data.adjusted_taxable_gifts)}</td>
          <td />
        </tr>
      </tbody>
    </table>
  );
}
