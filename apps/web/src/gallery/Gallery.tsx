import {
  Badge,
  Button,
  type Column,
  DataTable,
  Drawer,
  Fieldset,
  Menu,
  Popover,
  Sheet,
  Status,
  Tooltip,
  toast,
} from "@abacus/ui";
import { type JSX, useState } from "react";

// The component gallery (TASK-101): every shared component in one place, for building and for
// checking the look. Dev builds only (the router leaves it out of production).

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
    status: "ready_for_review",
    amount: 161345.67,
  },
  { id: "r2", name: "General ledger detail", status: "needs_revision", amount: 218000 },
  { id: "r3", name: "Bank confirmations", status: "open", amount: 52345.67 },
  { id: "r4", name: "Fixed asset roll-forward", status: "accepted", amount: 1200 },
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
    cell: (r) => r.amount.toLocaleString("en-US", { minimumFractionDigits: 2 }),
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

export function Gallery(): JSX.Element {
  const [drawer, setDrawer] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  return (
    <div className="flex flex-col gap-3">
      <h1 className="px-1 text-[20px] font-medium tracking-[-0.015em]">Components</h1>
      <Section title="Buttons and status">
        <div className="flex flex-wrap items-center gap-2">
          <Button>Primary</Button>
          <Button variant="outline">Secondary</Button>
          <Button variant="tonal">Tonal</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Destructive</Button>
          <Button variant="success">Approve</Button>
          <Badge tone="warning">Badge</Badge>
          <Status domain="workpaper" value="ready" />
          <Status domain="result" value="exception" />
        </div>
      </Section>
      <Section title="Overlays">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setDrawer(true);
            }}
          >
            Open drawer
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setSheet(true);
            }}
          >
            Open sheet
          </Button>
          <Popover trigger={<Button variant="outline">Popover</Button>} label="Example">
            <p className="text-ink-2">
              A card anchored to its trigger, for small forms and detail.
            </p>
          </Popover>
          <Menu
            label="Row actions"
            trigger={<Button variant="outline">Menu</Button>}
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
            variant="outline"
            onClick={() => {
              toast.show("Saved");
            }}
          >
            Toast
          </Button>
          <Button
            variant="outline"
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
            <Button size="sm" variant="outline">
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
        meta={<Status domain="request" value="ready_for_review" />}
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
