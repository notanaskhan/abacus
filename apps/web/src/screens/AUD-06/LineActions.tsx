// AUD-06's line actions on P-04 fields (A-02-T35; A-02 §3.6 AC-6.1, AC-6.2, AC-6.4). A line's
// field is `wp_ref:<account>` or `area_override:<account>` (C3 `register_field_owner`): Agree to
// source… finds the line in the viewer's document, writes the C4 reference and an L1 field tick
// as the person; Mark reviewed writes an L2 tick (P-04 refuses it to the line's preparer); Edit…
// changes the WP ref or the area with a required reason. Amounts are never fields (ADR-004): this
// file edits no amount. Loaded on demand by TrialBalance.tsx (the firm entry is at its budget).

import type { TbLayerLineOut } from "@abacus/api-client";
import {
  fieldEditMutation,
  fieldProvenanceOptions,
  fieldReferenceMutation,
  fieldTickMutation,
  viewerSearchOptions,
} from "@abacus/api-client/query";
import { Button, Dialog, Menu, prose } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

const TARGET = "trial_balance";
const FIELD = "h-[26px] w-full rounded-tile bg-card px-[8px] text-body text-ink";

/** One labelled text box (the TB's reason input's look, TbLive). */
function TextBox({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <>
      <label htmlFor={id} className="text-meta text-ink-2">
        {label}
      </label>
      <input
        id={id}
        value={value}
        maxLength={500}
        onChange={(e) => {
          onChange(e.target.value);
        }}
        className={FIELD}
      />
    </>
  );
}

/** The P-04 field key a line's annotation lives under. */
export function fieldKey(name: "wp_ref" | "area_override", account: string): string {
  return `${name}:${account}`;
}

function path(
  tbId: string,
  key: string,
): {
  target_type: string;
  target_id: string;
  field_key: string;
} {
  return { target_type: TARGET, target_id: tbId, field_key: key };
}

export interface LineActionsProps {
  tbId: string;
  line: TbLayerLineOut;
  /** The evidence version open in the dock's viewer; null when none is. */
  sourceVersionId: string | null;
}

/** The row's menu: Agree to source…, Mark reviewed (L2) when the person may, Edit…. */
export function LineActions({ tbId, line, sourceVersionId }: LineActionsProps): JSX.Element {
  const [open, setOpen] = useState<"agree" | "edit" | null>(null);
  const queryClient = useQueryClient();
  const key = fieldKey("wp_ref", line.account_code);
  const provenance = useQuery(fieldProvenanceOptions({ path: path(tbId, key) }));
  const tick = useMutation({
    ...fieldTickMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries();
    },
  });
  const allowed = provenance.data?.allowed_actions ?? [];
  const review = (): void => {
    const p = provenance.data;
    if (p === undefined) return;
    tick.mutate({
      path: path(tbId, key),
      body: { level: "L2_reviewer", seen_hash: p.content_hash },
    });
  };
  return (
    <>
      <Menu
        label={COPY.lineActions(line.account_name)}
        trigger={
          <button
            type="button"
            aria-label={COPY.lineActions(line.account_name)}
            data-line-actions={line.account_code}
            className="ml-[6px] text-ink-3"
          >
            ⋯
          </button>
        }
        sections={[
          [
            {
              label: COPY.agreeToSource,
              opensDialog: true,
              disabled: !allowed.includes("field.add_reference"),
              onSelect: () => {
                setOpen("agree");
              },
            },
            ...(allowed.includes("field.sign_off")
              ? [{ label: COPY.markReviewed, onSelect: review }]
              : []),
            {
              label: COPY.editLine,
              opensDialog: true,
              disabled: !allowed.includes("field.edit"),
              onSelect: () => {
                setOpen("edit");
              },
            },
          ],
        ]}
      />
      {open === "agree" && (
        <AgreeDialog
          tbId={tbId}
          line={line}
          sourceVersionId={sourceVersionId}
          onClose={() => {
            setOpen(null);
          }}
        />
      )}
      {open === "edit" && (
        <EditDialog
          tbId={tbId}
          line={line}
          onClose={() => {
            setOpen(null);
          }}
        />
      )}
    </>
  );
}

/** AC-6.1: find the line's amount in the viewer's document, pick the hit, agree. */
function AgreeDialog({
  tbId,
  line,
  sourceVersionId,
  onClose,
}: LineActionsProps & { onClose: () => void }): JSX.Element {
  const queryClient = useQueryClient();
  const key = fieldKey("wp_ref", line.account_code);
  // The line's amount as a document prints it ("1,606,560.00"): the search's first query.
  const [query, setQuery] = useState(prose(line.eoy, "cents"));
  const [page, setPage] = useState<number | null>(null);
  const provenance = useQuery(fieldProvenanceOptions({ path: path(tbId, key) }));
  const hits = useQuery({
    ...viewerSearchOptions({
      path: { version_id: sourceVersionId ?? "" },
      query: { q: query },
    }),
    enabled: sourceVersionId !== null && query.trim().length > 0,
  });
  const reference = useMutation(fieldReferenceMutation());
  const tick = useMutation(fieldTickMutation());
  const agree = async (): Promise<void> => {
    const p = provenance.data;
    if (p === undefined || sourceVersionId === null || page === null) return;
    await reference.mutateAsync({
      path: path(tbId, key),
      body: { document_id: sourceVersionId, page, seen_seq: p.current_seq },
    });
    await tick.mutateAsync({
      path: path(tbId, key),
      body: { level: "L1_preparer", seen_hash: p.content_hash },
    });
    void queryClient.invalidateQueries();
    onClose();
  };
  const pages = [...new Set((hits.data?.items ?? []).map((h) => h.page))];
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.agreeTitle(line.account_name)}
      action={
        <Button
          variant="primary"
          disabled={page === null || provenance.data === undefined}
          onClick={() => void agree()}
        >
          {COPY.agreeAction}
        </Button>
      }
    >
      {sourceVersionId === null ? (
        <p className="text-meta text-ink-3">{COPY.agreeNoSource}</p>
      ) : (
        <div className="flex flex-col gap-[8px]">
          <TextBox
            id="aud06-agree-q"
            label={COPY.agreeSearch}
            value={query}
            onChange={(v) => {
              setQuery(v);
              setPage(null);
            }}
          />
          {hits.data !== undefined && pages.length === 0 && (
            <p className="text-meta text-ink-3">{COPY.agreeNoHits}</p>
          )}
          <ul className="flex flex-col gap-[4px]">
            {pages.map((n) => (
              <li key={n}>
                <button
                  type="button"
                  aria-pressed={page === n}
                  onClick={() => {
                    setPage(n);
                  }}
                  className="text-left text-body"
                >
                  {COPY.agreeHit(n)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Dialog>
  );
}

/** AC-6.4: the WP ref and the area, each with the one required reason; amounts locked. */
function EditDialog({
  tbId,
  line,
  onClose,
}: {
  tbId: string;
  line: TbLayerLineOut;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [wpRef, setWpRef] = useState(line.wp_ref ?? "");
  const [area, setArea] = useState(line.area ?? "");
  const [reason, setReason] = useState("");
  const wpKey = fieldKey("wp_ref", line.account_code);
  const areaKey = fieldKey("area_override", line.account_code);
  const wpSeen = useQuery(fieldProvenanceOptions({ path: path(tbId, wpKey) }));
  const areaSeen = useQuery(fieldProvenanceOptions({ path: path(tbId, areaKey) }));
  const edit = useMutation(fieldEditMutation());
  const changes: Array<[string, string, number | undefined]> = [];
  if (wpRef !== (line.wp_ref ?? "")) changes.push([wpKey, wpRef, wpSeen.data?.current_seq]);
  if (area !== (line.area ?? "")) changes.push([areaKey, area, areaSeen.data?.current_seq]);
  const ready =
    reason.trim().length > 0 && changes.length > 0 && changes.every(([, , s]) => s !== undefined);
  const save = async (): Promise<void> => {
    for (const [key, value, seen] of changes) {
      await edit.mutateAsync({
        path: path(tbId, key),
        body: {
          value: { t: "text", v: value.trim() === "" ? null : value.trim() },
          citation_note: reason.trim(),
          seen_seq: seen ?? 0,
        },
      });
    }
    void queryClient.invalidateQueries();
    onClose();
  };
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.editTitle(line.account_name)}
      description={COPY.amountsLocked}
      dirty={changes.length > 0 || reason.length > 0}
      action={
        <Button variant="primary" disabled={!ready} onClick={() => void save()}>
          {COPY.save}
        </Button>
      }
    >
      <div className="flex flex-col gap-[8px]">
        <TextBox id="aud06-wp-ref" label={COPY.wpRef} value={wpRef} onChange={setWpRef} />
        <TextBox id="aud06-area" label={COPY.areaOverride} value={area} onChange={setArea} />
        <TextBox id="aud06-reason" label={COPY.reason} value={reason} onChange={setReason} />
      </div>
    </Dialog>
  );
}
