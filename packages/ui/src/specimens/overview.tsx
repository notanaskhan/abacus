import { type JSX, useState } from "react";
import { Amount } from "../components/amount";
import { Button } from "../components/button";
import { type Column, DataTable } from "../components/data-table";
import { Drawer, Fieldset, Sheet } from "../components/overlays";
import { Menu, Popover, Tooltip } from "../components/popover";
import { Badge } from "../components/surfaces";
import { toast } from "../components/toast";
import { Status } from "../components/status";

// The component gallery's first specimen (TASK-101, moved here by F-05-T09): every shared
// component in one place, for building and for checking the look. Reached only through
// "@abacus/ui/specimens", which production never imports.

interface Row {
  id: string;
  name: string;
  status: string;
  amount: number;
}

const ROWS: Row[] = [
  {
    id: "r1",
    name: "Trial balance as of year end",
    status: "uploaded",
    amount: 161345.67,
  },
  { id: "r2", name: "General ledger detail", status: "returned", amount: 218000 },
  { id: "r3", name: "Bank confirmations", status: "requested", amount: 52345.67 },
  { id: "r4", name: "Fixed asset roll-forward", status: "received", amount: 1200 },
];

const COLUMNS: Column<Row>[] = [
  { key: "name", header: "Request", cell: (r) => r.name, sortValue: (r) => r.name },
  {
    key: "status",
    header: "Status",
    cell: (r) => <Status domain="request" value={r.status} />,
    sortValue: (r) => r.status,
  },
  {
    key: "amount",
    header: "Amount",
    align: "right",
    cell: (r) => <Amount value={r.amount} style="cents" zero="explicit" />,
    sortValue: (r) => r.amount,
  },
];

function Section({
  title,
  children,
}: {
  title: string;
  children: JSX.Element | JSX.Element[];
}): JSX.Element {
  return (
    <section className="flex flex-col gap-3 rounded-pane bg-card p-4 shadow-e2">
      <h2 className="text-[14.5px] font-medium">{title}</h2>
      {children}
    </section>
  );
}

export function Overview(): JSX.Element {
  const [drawer, setDrawer] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  return (
    <div className="flex flex-col gap-3">
      <Section title="Buttons and status">
        <div className="flex flex-wrap items-center gap-2">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="tonal">Tonal</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="success">Approve</Button>
          <Badge tone="warning">Badge</Badge>
          <Status domain="workpaper" value="ready" />
          <Status domain="result" value="exception" />
        </div>
      </Section>
      <Section title="Overlays">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setDrawer(true);
            }}
          >
            Open drawer
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setSheet(true);
            }}
          >
            Open sheet
          </Button>
          <Popover trigger={<Button variant="secondary">Popover</Button>} label="Example">
            <p className="text-ink-2">
              A card anchored to its trigger, for small forms and detail.
            </p>
          </Popover>
          <Menu
            label="Row actions"
            trigger={<Button variant="secondary">Menu</Button>}
            sections={[
              [
                { label: "Open", onSelect: () => undefined },
                { label: "Copy link", onSelect: () => undefined, hint: "To this request" },
              ],
              [{ label: "Void…", onSelect: () => undefined, danger: true }],
            ]}
          />
          <Tooltip content="Prepared by Sam Staff on Oct 20">
            <Button variant="ghost">Tooltip</Button>
          </Tooltip>
          <Button
            variant="secondary"
            onClick={() => {
              toast.show("Saved");
            }}
          >
            Toast
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              toast.deferred("Follow-up sent to 3 contacts", () => {
                toast.show("Sent");
              });
            }}
          >
            Toast with Undo
          </Button>
        </div>
      </Section>
      <section className="overflow-hidden rounded-pane bg-card shadow-e2">
        <DataTable
          label="Example requests"
          rows={ROWS}
          columns={COLUMNS}
          rowKey={(r) => r.id}
          selectable
          selected={picked}
          onSelectedChange={setPicked}
          bulkActions={(ids) => (
            <Button size="sm" variant="secondary">
              {`Remind ${String(ids.length)}`}
            </Button>
          )}
          onRowClick={() => {
            setDrawer(true);
          }}
        />
      </section>
      <Drawer
        open={drawer}
        onOpenChange={setDrawer}
        title="Trial balance as of year end"
        meta={<Status domain="request" value="uploaded" />}
        footer={<Button>Accept</Button>}
      >
        <Fieldset title="Details">
          <p className="text-ink-2">Financial statements · Tier A</p>
        </Fieldset>
        <Fieldset title="Evidence">
          <p className="text-ink-2">Version 1 · Excel · 6 KB</p>
        </Fieldset>
      </Drawer>
      <Sheet
        open={sheet}
        onOpenChange={setSheet}
        title="Draft follow-up"
        meta={<Button size="sm">Send</Button>}
      >
        <Fieldset title="To">
          <p>Casey Client</p>
        </Fieldset>
        <Fieldset title="Message">
          <p className="text-ink-2">3 items are still outstanding.</p>
        </Fieldset>
      </Sheet>
    </div>
  );
}
