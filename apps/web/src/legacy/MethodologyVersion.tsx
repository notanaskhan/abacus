import type { TemplateItemOut } from "@abacus/api-client";
import { firmMembersOptions, getVersionOptions } from "@abacus/api-client/query";
import { AiTag, Alert, Panel, Skeleton, Table, Td, Th } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { JSX } from "react";
import { errorMessage } from "../api";
import { TemplateGuidanceDrafts } from "./TemplateGuidanceDrafts";

// SPEC-035 Q3 (TASK-074): approved drafted guidance carries its label wherever the firm reads it.
function Guidance({
  item,
  names,
}: {
  item: TemplateItemOut;
  names: Map<string, string>;
}): JSX.Element {
  if (!item.why && !item.good_looks_like) return <span className="text-ink-3">None</span>;
  if (item.guidance_source !== "drafted") return <span>Written</span>;
  const approver = item.guidance_approved_by
    ? (names.get(item.guidance_approved_by) ?? "your team")
    : "your team";
  return (
    <span className="flex items-center gap-1">
      <AiTag />
      {`Drafted via Agent, approved by ${approver}`}
    </span>
  );
}

export function MethodologyVersion({ versionId }: { versionId: string }): JSX.Element {
  const version = useQuery(getVersionOptions({ path: { version_id: versionId } }));
  const members = useQuery({ ...firmMembersOptions(), retry: false });
  if (version.isPending) return <Skeleton className="h-64" />;
  if (version.isError) {
    return <Alert title="Couldn't load this version">{errorMessage(version.error)}</Alert>;
  }
  const v = version.data;
  const names = new Map((members.data ?? []).map((m) => [m.user_id, m.display_name]));
  return (
    <div className="flex flex-col gap-4">
      <nav aria-label="Breadcrumb" className="text-body text-ink-3">
        <Link to="/admin/methodology" className="hover:underline">
          Methodology
        </Link>{" "}
        / {v.summary.template_name} v{v.summary.version}
      </nav>
      <h1 className="text-[15px] font-medium tracking-[-0.012em]">
        {v.summary.template_name} <span className="text-ink-3">v{v.summary.version}</span>
      </h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={`Areas (${String(v.areas.length)})`}>
          <Table>
            <thead>
              <tr>
                <Th>Code</Th>
                <Th>Name</Th>
              </tr>
            </thead>
            <tbody>
              {v.areas.map((a) => (
                <tr key={a.code}>
                  <Td className="tabular-nums">{a.code}</Td>
                  <Td>{a.name}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Panel>
        <Panel title={`Account rules (${String(v.rules.length)})`}>
          <Table>
            <thead>
              <tr>
                <Th>Area</Th>
                <Th>From</Th>
                <Th>To</Th>
              </tr>
            </thead>
            <tbody>
              {v.rules.map((r) => (
                <tr key={`${r.area_code}-${r.account_from}`}>
                  <Td>{r.area_code}</Td>
                  <Td className="tabular-nums">{r.account_from}</Td>
                  <Td className="tabular-nums">{r.account_to}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Panel>
      </div>
      <Panel title={`Standard requests (${String(v.items.length)})`}>
        <div className="overflow-x-auto">
          <Table className="min-w-[560px]">
            <thead>
              <tr>
                <Th>Area</Th>
                <Th>Request</Th>
                <Th>Tier</Th>
                <Th>Guidance</Th>
              </tr>
            </thead>
            <tbody>
              {v.items.map((i, index) => (
                <tr key={`${i.area_code}-${String(index)}`}>
                  <Td>{i.area_code}</Td>
                  <Td>{i.description}</Td>
                  <Td>{i.tier}</Td>
                  <Td className="text-meta">
                    <Guidance item={i} names={names} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Panel>
      <TemplateGuidanceDrafts versionId={versionId} items={v.items} />
    </div>
  );
}
