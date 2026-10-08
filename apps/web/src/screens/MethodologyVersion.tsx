import { getVersionOptions } from "@abacus/api-client/query";
import { Alert, Panel, Skeleton, Table, Td, Th } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { JSX } from "react";
import { errorMessage } from "../api";

export function MethodologyVersion({ versionId }: { versionId: string }): JSX.Element {
  const version = useQuery(getVersionOptions({ path: { version_id: versionId } }));
  if (version.isPending) return <Skeleton className="h-64" />;
  if (version.isError) {
    return <Alert title="Couldn't load this version">{errorMessage(version.error)}</Alert>;
  }
  const v = version.data;
  return (
    <div className="flex flex-col gap-4">
      <nav aria-label="Breadcrumb" className="text-sm text-muted">
        <Link to="/admin/methodology" className="hover:underline">
          Methodology
        </Link>{" "}
        / {v.summary.template_name} v{v.summary.version}
      </nav>
      <h1 className="text-3xl">
        {v.summary.template_name} <span className="text-muted">v{v.summary.version}</span>
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
              </tr>
            </thead>
            <tbody>
              {v.items.map((i, index) => (
                <tr key={`${i.area_code}-${String(index)}`}>
                  <Td>{i.area_code}</Td>
                  <Td>{i.description}</Td>
                  <Td>{i.tier}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Panel>
    </div>
  );
}
