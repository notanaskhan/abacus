import type { ItemRequestPreviewOut, ItemRequestsIn, SampleSetOut } from "@abacus/api-client";
import {
  sampleItemRequestsMutation,
  sampleItemRequestsPreviewMutation,
  sampleSetOptions,
} from "@abacus/api-client/query";
import { Button, Fieldset, Icon, Segmented, SheetModal, ValueRow, count, toast } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useMemo, useState } from "react";
import { useClientContacts } from "../../domain/requests";
import { COPY } from "./copy";

// AUD-11 c · Generate item requests (A-03-T15; the handoff's GENERATE SHEET, O3 500 wide): one
// request per template per sampled item, from an approved version only (C9's fan-out). The counts
// are the server's preview ("125 requests · 100 to POR-03 · 25 to POR-14", ADR-050); Create posts
// the same body once under one Idempotency-Key, so a retry never doubles the requests. A person
// creates them; nothing here is the agent's (INV-1).

export interface SheetTemplate {
  description: string;
  /** The client contact the request goes to (POR-03), or the third party it is delegated to. */
  contactId: string | null;
  thirdParty: boolean;
}

const EMPTY: SheetTemplate = { description: "", contactId: null, thirdParty: false };

function body(templates: readonly SheetTemplate[], due: string): ItemRequestsIn | null {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(due) || templates.length === 0) return null;
  if (templates.some((t) => t.description.trim() === "" || t.contactId === null)) return null;
  return {
    templates: templates.map((t) =>
      t.thirdParty
        ? { description: t.description.trim(), third_party_contact_id: t.contactId }
        : { description: t.description.trim(), contact_id: t.contactId },
    ),
    due_on: due,
    wave: "sample",
  };
}

export function GenerateSheet({
  set,
  open,
  onOpenChange,
  initial,
  due: initialDue,
}: {
  set: SampleSetOut;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The templates the sheet opens with (the artboard's five; a new sheet starts with one). */
  initial?: readonly SheetTemplate[];
  due?: string;
}): JSX.Element {
  const contacts = useClientContacts(set.engagement_id).data ?? [];
  const [templates, setTemplates] = useState<readonly SheetTemplate[]>(initial ?? [EMPTY]);
  const [due, setDue] = useState(initialDue ?? "");
  const [key, setKey] = useState(() => crypto.randomUUID());
  const queries = useQueryClient();
  const path = { sample_set_id: set.id, version_no: set.version_no };
  const { id: setId, version_no: versionNo } = set;
  const preview = useMutation(sampleItemRequestsPreviewMutation());
  const create = useMutation(sampleItemRequestsMutation());
  const asked = useMemo(() => body(templates, due), [templates, due]);
  const askedKey = asked === null ? null : JSON.stringify(asked);
  const { mutate } = preview;
  useEffect(() => {
    if (!open || askedKey === null) return;
    mutate({
      path: { sample_set_id: setId, version_no: versionNo },
      body: JSON.parse(askedKey) as ItemRequestsIn,
    });
  }, [open, askedKey, mutate, setId, versionNo]);
  const shown: ItemRequestPreviewOut | undefined = asked === null ? undefined : preview.data;
  const total = shown?.total ?? 0;
  const change = (i: number, next: Partial<SheetTemplate>): void => {
    setTemplates((all) => all.map((t, n) => (n === i ? { ...t, ...next } : t)));
  };
  const close = (next: boolean): void => {
    onOpenChange(next);
    if (!next) {
      setTemplates(initial ?? [EMPTY]);
      setDue(initialDue ?? "");
      setKey(crypto.randomUUID());
      preview.reset();
      create.reset();
    }
  };
  const submit = (): void => {
    if (asked === null) return;
    create.mutate(
      { path, body: asked, headers: { "Idempotency-Key": key } },
      {
        onSuccess: (made) => {
          toast.show(COPY.generate.created(count(String(made.created))));
          void queries.invalidateQueries({ queryKey: sampleSetOptions({ path }).queryKey });
          close(false);
        },
      },
    );
  };
  return (
    <SheetModal
      open={open}
      onOpenChange={close}
      title={COPY.generate.title}
      dirty={templates !== (initial ?? [EMPTY]) || due !== (initialDue ?? "")}
      footer={
        <Button
          variant="primary"
          disabled={asked === null || shown === undefined || total === 0 || create.isPending}
          onClick={submit}
        >
          {COPY.generate.create(count(String(total)))}
        </Button>
      }
    >
      <Fieldset title={COPY.generate.per(set.items_total === 0 ? 0 : templates.length)} flush>
        {templates.map((t, i) => (
          <div key={i} data-aud11="template" className="hairline-b last:border-b-0">
            <ValueRow
              kind="text"
              label={COPY.generate.request(i + 1)}
              value={t.description}
              placeholder={COPY.generate.requestPlaceholder}
              onChange={(v) => {
                change(i, { description: v });
              }}
            />
            <ValueRow
              kind="select"
              indented
              label={COPY.generate.recipientLabel}
              placeholder={COPY.generate.choose}
              options={contacts.map((c) => ({
                value: c.id,
                label: c.display_name ?? c.email ?? c.id,
                hint: c.role,
              }))}
              {...(t.contactId === null ? {} : { value: t.contactId })}
              onChange={(v) => {
                change(i, { contactId: v });
              }}
            />
            <ValueRow
              kind="toggle"
              indented
              label={COPY.generate.thirdParty}
              checked={t.thirdParty}
              onChange={(on) => {
                change(i, { thirdParty: on });
              }}
            />
          </div>
        ))}
        <div className="flex items-center gap-[8px] px-[12px] py-[6px]">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setTemplates((all) => [...all, EMPTY]);
            }}
          >
            <Icon name="plus" size={12} />
            {COPY.generate.add}
          </Button>
          {templates.length > 1 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setTemplates((all) => all.slice(0, -1));
              }}
            >
              {COPY.generate.remove}
            </Button>
          )}
        </div>
      </Fieldset>
      <Fieldset flush>
        <ValueRow
          kind="text"
          label={COPY.generate.due}
          value={due}
          placeholder={COPY.generate.datePlaceholder}
          onChange={setDue}
        />
        <ValueRow kind="info" label={COPY.generate.wave}>
          <Segmented
            label={COPY.generate.wave}
            size="small"
            active={COPY.generate.sampleWave}
            options={[COPY.generate.sampleWave]}
          />
        </ValueRow>
      </Fieldset>
      <p role="status" data-aud11="generate-preview" className="px-[4px] text-dense text-ink-2">
        {shown === undefined
          ? COPY.generate.previewEmpty
          : COPY.generate.preview(
              count(String(shown.total)),
              count(String(shown.by_surface["POR-03"] ?? 0)),
              count(String(shown.by_surface["POR-14"] ?? 0)),
            )}
      </p>
      {shown !== undefined && shown.recipients.length > 0 && (
        <ul
          data-aud11="recipients"
          className="flex flex-col gap-[2px] px-[4px] text-meta text-ink-3"
        >
          {shown.recipients.map((r) => (
            <li key={`${r.name}-${r.surface}`}>
              {COPY.generate.recipient(
                r.organisation == null ? r.name : `${r.name}, ${r.organisation}`,
                count(String(r.requests)),
                r.surface,
              )}
            </li>
          ))}
        </ul>
      )}
      {(preview.isError || create.isError) && (
        <p role="alert" className="px-[4px] text-dense text-red-ink">
          {COPY.generate.failed}
        </p>
      )}
    </SheetModal>
  );
}
