// AUD-28 · Consultations log (Q-05-T20, TASK-8826; docs/screens/AUD-28.md; handoff AUD-28): T9
// close-review preset at firm level at /audits/consultations and /audits/$auditId/consultations.
// The queue bands Open and Concluded; the detail shows the question, facts, conclusion, links and,
// for C-04, the difference of opinion resolved before release; the decision pane is read-only.
// f New consultation (the consultee picker lists partners and specialists only: never the agent,
// never a walled person, the server checks again); g Record conclusion (disabled until a
// conclusion and the implemented toggle are set). The agent is never consulted and never concludes.
import type { ConsultationLogRowOut } from "@abacus/api-client";
import { consultationConcludeMutation, consultationDetailOptions, consultationsLogOptions } from "@abacus/api-client/query";
import { Button, Dialog, EmptyState, Pill, Skeleton, Toggle, cn } from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY as C } from "./copy";

export interface Consultee {
  userId: string;
  label: string;
}

export interface AUD28Props {
  /** d: opened from an engagement (AUD-19 or AUD-18): that engagement's name and id. */
  engagement?: { id: string; name: string };
  selectedRef?: string | null;
  /** f and g: a sheet open on arrival. */
  initial?: "new" | "conclude";
  /** The firm's partners and specialists (the agent and walled people never appear). */
  consultees?: readonly Consultee[];
  engagementNames?: Readonly<Record<string, string>>;
}

function Band({ title, n }: { title: string; n: number }): JSX.Element {
  return <h3 className="flex h-[31px] items-center gap-[6px] bg-band-hd px-[12px] text-[12px] font-medium">{title}<span className="text-ink-3">{n}</span></h3>;
}

export function AUD28({ engagement, selectedRef, initial, consultees = [], engagementNames = {} }: AUD28Props): JSX.Element {
  const log = useQuery(consultationsLogOptions(engagement ? { query: { engagement_id: engagement.id } } : undefined));
  const [picked, setPicked] = useState<string | null | undefined>(selectedRef);
  const [sheet, setSheet] = useState<"new" | "conclude" | undefined>(initial);
  const [text, setText] = useState("");
  const [implemented, setImplemented] = useState(false);
  const [consultee, setConsultee] = useState<string>("");
  const rows = log.data?.items ?? [];
  const selected = rows.find((r) => r.ref === picked) ?? rows[0];
  const detail = useQuery({
    ...consultationDetailOptions({ path: { consultation_id: selected?.consultation_id ?? "" } }),
    enabled: selected !== undefined,
  });
  const conclude = useMutation(consultationConcludeMutation());
  if (log.data === undefined) return <Skeleton aria-label={C.title} className="h-[700px] w-full" />;
  const open = rows.filter((r) => r.status === "open");
  const done = rows.filter((r) => r.status === "concluded");
  const d = detail.data;
  const row = (r: ConsultationLogRowOut): JSX.Element => (
    <button key={r.consultation_id} type="button" data-aud28="row" aria-selected={r.ref === selected?.ref}
      onClick={() => { setPicked(r.ref); }}
      className={cn("flex min-h-[52px] w-full flex-col justify-center border-t border-hair px-[12px] text-left text-[13px]", r.ref === selected?.ref && "bg-selected")}>
      <span>{`${r.ref} — ${r.question ?? ""}`}</span>
      <span className="text-[11.5px] text-ink-3">{`${r.status === "open" ? C.open : C.concluded} · ${engagementNames[r.engagement_id ?? ""] ?? ""}`}</span>
    </button>
  );
  return (
    <div data-screen="AUD-28" className="flex flex-col">
      <div className="flex h-[42px] items-center justify-center gap-[8px] text-[15px] font-medium">
        {C.title}<span className="font-normal text-ink-2">{C.subtitle}</span>
      </div>
      <div className="flex h-[50px] items-center gap-[8px] px-[12px] text-[12.5px]">
        <span className={cn("rounded-pill px-[10px] py-[4px] shadow-e1", engagement ? "bg-amber-tint" : "bg-card")} data-aud28="engagement-chip">
          {`${C.chips.engagement} │ ${engagement?.name ?? C.all}`}
        </span>
        <span className="rounded-pill bg-card px-[10px] py-[4px] shadow-e1">{`${C.chips.status} │ ${C.all}`}</span>
        <span className="rounded-pill bg-card px-[10px] py-[4px] shadow-e1">{`${C.chips.consulted} │ ${C.anyone}`}</span>
        <span className="rounded-pill bg-card px-[10px] py-[4px] shadow-e1">{`${C.chips.year} │ 2026`}</span>
        <span className="flex-1" />
        <Button variant="secondary" size="sm" onClick={() => { setSheet("new"); }}>{C.newConsultation}</Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title={C.emptyTitle}>{C.emptyBody}</EmptyState>
      ) : (
        <div className="flex gap-[10px] p-[10px]">
          <section aria-label={C.queue} className="flex flex-[790] rounded-card bg-card shadow-e1">
            <div className="w-[310px] border-r border-hair">
              <h2 className="flex h-[46px] items-center justify-center text-[13.5px] font-medium">{C.queue}</h2>
              {open.length > 0 ? <Band title={C.open} n={open.length} /> : null}
              {open.map(row)}
              {done.length > 0 ? <Band title={C.concluded} n={done.length} /> : null}
              {done.map(row)}
            </div>
            {selected ? (
              <div className="flex w-[480px] flex-col" data-aud28="detail">
                <p className="bg-nested px-[14px] py-[12px] text-[15px] font-medium">{selected.question}</p>
                <dl className="text-[13px]">
                  {[[C.kv.engagement, engagementNames[selected.engagement_id ?? ""] ?? ""], [C.kv.raisedBy, selected.raised_by_name], [C.kv.consultedWith, selected.consulted_with_name]].map(([k, v]) => (
                    <div key={k} className="flex h-[35px] items-center border-t border-hair px-[14px]"><dt className="w-[140px] text-ink-3">{k}</dt><dd>{v}</dd></div>
                  ))}
                  <div className="flex h-[35px] items-center border-t border-hair px-[14px]"><dt className="w-[140px] text-ink-3">{C.kv.status}</dt><dd><Pill variant={selected.status === "open" ? "amber" : "green-tint"}>{selected.status === "open" ? C.open : C.concluded}</Pill></dd></div>
                  {d?.implemented ? <div className="flex h-[35px] items-center border-t border-hair px-[14px]"><dt className="w-[140px] text-ink-3">{C.kv.implemented}</dt><dd>{`Yes · ${d.implemented_reference ?? ""}`}</dd></div> : null}
                </dl>
                {d?.facts ? (<><Band title={C.questionFacts} n={1} /><p className="px-[14px] py-[8px] text-[12.5px] text-ink-2">{d.facts}</p></>) : null}
                {selected.conclusion ? (<><Band title={C.conclusion} n={1} /><p className="px-[14px] py-[8px] text-[12.5px] text-ink-2" data-aud28="conclusion">{selected.conclusion}</p></>) : null}
                {d && d.positions.length > 0 ? (
                  <div className="m-[10px] rounded-[10px] bg-amber-tint p-[10px] text-[12.5px]" data-aud28="difference">
                    <strong>{C.difference}</strong>
                    {d.positions.map((p) => <p key={p.recorded_by_name}>{`${p.recorded_by_name} (${p.role === "eqr_reviewer" ? "EQR" : "Engagement Partner"}): ${p.position}`}</p>)}
                    {d.resolution ? <p>{C.resolvedBy(d.resolution.resolved_by_name, d.resolution.resolution)}</p> : null}
                  </div>
                ) : null}
                {d && d.links.length > 0 ? (<><Band title={C.linked} n={d.links.length} /><div className="flex flex-wrap gap-[6px] px-[14px] py-[8px]">{d.links.map((l) => <Pill key={l.target_id} variant="tag">{l.linked_by_name}</Pill>)}</div></>) : null}
                <footer className="mt-auto flex flex-col gap-[6px] p-[10px]">
                  {selected.status === "open" ? (
                    <Button variant="primary" onClick={() => { setSheet("conclude"); }}>{C.recordConclusion}</Button>
                  ) : (
                    <><Button variant="primary" disabled>{C.recorded}</Button><Button variant="secondary">{C.reopen}</Button></>
                  )}
                </footer>
              </div>
            ) : null}
          </section>
          <section aria-label={C.linkedDecision} className="flex-[576] rounded-card bg-card shadow-e1">
            <h2 className="flex h-[46px] items-center justify-center text-[13.5px] font-medium">{C.linkedDecision}</h2>
            {d && d.links.some((l) => l.kind === "decision_card") ? (
              <p className="p-[12px] text-[12.5px]">{d.links.find((l) => l.kind === "decision_card")?.linked_by_name}</p>
            ) : (
              <EmptyState title={C.noDecision} action={<Button variant="secondary" size="sm">{C.linkDecision}</Button>} />
            )}
          </section>
        </div>
      )}
      <Dialog open={sheet === "new"} onOpenChange={(o) => { setSheet(o ? "new" : undefined); }} title={C.sheet.title} description={C.sheet.consulteeHelp}>
        <label className="flex flex-col gap-[4px] p-[12px] text-[12.5px]">
          {C.sheet.consultee}
          <select data-aud28="consultee" value={consultee} onChange={(e) => { setConsultee(e.target.value); }}>
            <option value="" />
            {consultees.map((c) => <option key={c.userId} value={c.userId}>{c.label}</option>)}
          </select>
        </label>
        <div className="flex justify-end p-[12px]"><Button variant="primary" disabled={consultee === ""}>{C.sheet.submit}</Button></div>
      </Dialog>
      <Dialog open={sheet === "conclude"} onOpenChange={(o) => { setSheet(o ? "conclude" : undefined); }} title={C.conclude.title}>
        <label className="flex flex-col gap-[4px] p-[12px] text-[12.5px]">
          {C.conclude.text}
          <textarea data-aud28="conclusion-text" value={text} onChange={(e) => { setText(e.target.value); }} />
        </label>
        <div className="px-[12px]"><Toggle label={C.conclude.implemented} checked={implemented} onChange={setImplemented} /></div>
        <div className="flex justify-end p-[12px]">
          <Button variant="primary" disabled={text.trim() === "" || !implemented}
            onClick={() => {
              if (!selected) return;
              conclude.mutate({ path: { consultation_id: selected.consultation_id }, body: { conclusion: text.trim(), implemented, implemented_reference: null } });
              setSheet(undefined);
            }}>
            {C.conclude.save}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
