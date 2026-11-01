import type { SampleItemOut } from "@abacus/api-client";
import {
  sampleItemRequestsMutation,
  sampleItemsOptions,
  sampleSetOptions,
  sampleSetsListOptions,
} from "@abacus/api-client/query";
import { Button, Fieldset, ValueRow, count, toast } from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { COPY } from "./copy";

// SHL-14 c · Sample-driven bulk (A-03-T15; the handoff's state 3, deferred to A-03 by P-06-T13):
// with the Sample wave on a new request, the composer offers the work item's approved sample
// versions only; the participants list card shows the first five names and "+ n more"; Create
// posts one template (this request) over every sampled item through C9's fan-out, under one
// Idempotency-Key. The client preview names no seed, size or parameter (INV-4); a person creates
// the requests (INV-1).

const SHOWN = 5;

export interface SampleWave {
  fields: ReactNode;
  /** Replaces the composer's footer while a sample is chosen. */
  footer: ReactNode | null;
}

export function useSampleWave({
  on,
  workItemId,
  title,
  assignee,
  assigneeName,
  delegate,
  thirdParty,
  due,
  onCreated,
}: {
  on: boolean;
  workItemId: string | undefined;
  title: string;
  assignee: string | null;
  assigneeName: string | undefined;
  delegate: string | null;
  thirdParty: boolean;
  due: string;
  onCreated: () => void;
}): SampleWave {
  const sets = useQuery({
    ...sampleSetsListOptions({ path: { work_item_id: workItemId ?? "" } }),
    enabled: on && workItemId !== undefined,
  });
  const approved = (sets.data?.items ?? []).filter((s) => s.status === "approved");
  const [chosen, setChosen] = useState<string | null>(null);
  const setId = chosen ?? approved[0]?.id ?? null;
  const set = useQuery({
    ...sampleSetOptions({ path: { sample_set_id: setId ?? "" } }),
    enabled: on && setId !== null,
  });
  const data = set.data?.status === "approved" ? set.data : undefined;
  const items = useQuery({
    ...sampleItemsOptions({
      path: { sample_set_id: data?.id ?? "", version_no: data?.version_no ?? 1 },
    }),
    enabled: on && data !== undefined,
  });
  const [key] = useState(() => crypto.randomUUID());
  const create = useMutation(sampleItemRequestsMutation());
  if (!on) return { fields: null, footer: null };

  const people: SampleItemOut[] = items.data?.items ?? [];
  const n = data?.items_total ?? 0;
  const recipient = thirdParty ? delegate : assignee;
  const ready =
    data !== undefined &&
    title.trim() !== "" &&
    recipient !== null &&
    /^\d{4}-\d{2}-\d{2}$/u.test(due);
  const submit = (): void => {
    if (!ready) return;
    create.mutate(
      {
        path: { sample_set_id: data.id, version_no: data.version_no },
        body: {
          templates: [
            thirdParty
              ? { description: title.trim(), third_party_contact_id: recipient }
              : { description: title.trim(), contact_id: recipient },
          ],
          due_on: due,
          wave: "sample",
        },
        headers: { "Idempotency-Key": key },
      },
      {
        onSuccess: (made) => {
          toast.show({ kind: "success", text: COPY.sample.created(count(String(made.created))) });
          onCreated();
        },
      },
    );
  };
  const fields = (
    <Fieldset title={COPY.sample.title} flush>
      <ValueRow
        kind="select"
        label={COPY.sample.picker}
        placeholder={approved.length === 0 ? COPY.sample.none : COPY.choose}
        options={approved.map((s) => ({
          value: s.id,
          label: COPY.sample.option(s.title, s.current_version_no, count(String(s.final_size))),
        }))}
        {...(setId === null ? {} : { value: setId })}
        onChange={setChosen}
      />
      {data !== undefined && (
        <>
          <ValueRow kind="value" label={COPY.sample.linked}>
            {COPY.sample.linkedValue(data.title, data.parameters.seed_hex)}
          </ValueRow>
          <div data-shl14="sample-list" className="px-[12px] py-[6px]">
            <p className="text-meta text-ink-3">{COPY.sample.count(count(String(n)))}</p>
            <ul className="mt-[4px] flex flex-col">
              {people.slice(0, SHOWN).map((p) => (
                <li key={p.position} className="flex h-[30px] items-center text-body">
                  {p.name ?? p.record_key}
                </li>
              ))}
              {n > SHOWN && (
                <li className="flex h-[30px] items-center text-meta text-ink-3">
                  {COPY.sample.more(n - SHOWN)}
                </li>
              )}
            </ul>
          </div>
          {assigneeName !== undefined && !thirdParty && (
            <p data-shl14="sample-preview" className="px-[12px] py-[6px] text-meta text-ink-2">
              {COPY.sample.preview(assigneeName.split(" ")[0] ?? assigneeName, count(String(n)))}
            </p>
          )}
        </>
      )}
    </Fieldset>
  );
  const footer =
    data === undefined ? null : (
      <div className="flex w-full items-center gap-[8px]">
        <span className="min-w-0 flex-1 text-meta text-ink-3">
          {create.isError ? COPY.toast.failed : COPY.sample.footer(count(String(n)))}
        </span>
        <Button variant="primary" size="sm" disabled={!ready || create.isPending} onClick={submit}>
          {COPY.sample.create(count(String(n)))}
        </Button>
      </div>
    );
  return { fields, footer };
}
