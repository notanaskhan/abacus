import { consentEvidence } from "@abacus/api-client";
import type { ConsentDetailOut } from "@abacus/api-client";
import { consentOptions } from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  PaperCard,
  Segmented,
  Sheet,
  SheetRow,
  Skeleton,
  date,
  time,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useSession } from "../../app-core/session";
import { COPY, DOCUMENT_HEADINGS, DOCUMENT_TABS, METHODS, PURPOSES, SET_PURPOSE } from "./copy";

// ADM-05 c · the evidence drawer (T-01-T32, part 2; docs/screens/ADM-05.md): the consent's facts
// (purpose, templates, who signed when, how, expiry, the agent's reads since signature) and one
// paper per signed document, switched by a Segmented: a standard set's two consents arrived in
// one envelope but are separate signed documents (Rev. Proc. 2013-14 §5.05). "Download evidence"
// fetches the signed document through the audited route (`consent.evidence_download`).

function signedLine(detail: ConsentDetailOut, now: Date, tz: string): string {
  return detail.signers
    .filter((s) => s.signed_at != null)
    .map((s) => {
      const at = s.signed_at ?? "";
      return `${s.name} ${date(at, { now, tz, withYear: true })} ${time(at, { tz, zone: true })}`;
    })
    .join(" · ");
}

function methodLine(detail: ConsentDetailOut): string {
  const used = [...new Set(detail.signers.flatMap((s) => (s.method == null ? [] : [s.method])))];
  const words = used.map((m) => METHODS[m] ?? m);
  return words.length === 0 ? "—" : `${COPY.drawer.esign}, ${words.join(" + ")}`;
}

export function EvidenceDrawer({
  consentId,
  client,
  now,
  onClose,
}: {
  consentId: string;
  client: string;
  now: Date;
  onClose: () => void;
}): JSX.Element {
  const tz = useSession().tz ?? DEFAULT_TZ;
  const detail = useQuery(consentOptions({ path: { consent_id: consentId } }));
  const data = detail.data;
  const documents = data?.documents ?? [];
  const tabs = documents.map((d) => DOCUMENT_TABS[d.purpose] ?? PURPOSES[d.purpose]);
  const [active, setActive] = useState<string | undefined>(undefined);
  const shown = documents[Math.max(0, tabs.indexOf(active ?? tabs[0] ?? ""))];

  const download = (): void => {
    if (shown === undefined) return;
    void consentEvidence({ path: { consent_id: consentId, document_id: shown.id } });
  };

  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.drawer.title(client)}
      action={
        <Button size="sm" variant="secondary" disabled={shown === undefined} onClick={download}>
          {COPY.drawer.download}
        </Button>
      }
    >
      {data === undefined ? (
        <Skeleton />
      ) : (
        <div data-drawer="consent-evidence" className="flex flex-col gap-[12px] p-[12px]">
          <dl className="rounded-pane bg-card shadow-e1">
            <SheetRow
              label={COPY.drawer.purpose}
              value={documents.length > 1 ? SET_PURPOSE : PURPOSES[data.consent.purpose]}
            />
            <SheetRow
              label={COPY.drawer.templates}
              value={[
                ...new Set(
                  documents.map(
                    (d) =>
                      (d.purpose === data.consent.purpose ? data.consent.template_name : null) ??
                      DOCUMENT_TABS[d.purpose] ??
                      d.purpose,
                  ),
                ),
              ].join("; ")}
            />
            <SheetRow label={COPY.drawer.signed} value={signedLine(data, now, tz) || "—"} />
            <SheetRow label={COPY.drawer.method} value={methodLine(data)} />
            <SheetRow
              label={COPY.drawer.expires}
              value={date(data.consent.expires_at, { now, tz, withYear: true })}
            />
            <SheetRow
              label={COPY.drawer.reads}
              value={COPY.drawer.readCount(data.agent_reads.length)}
            />
          </dl>
          {tabs.length > 1 && (
            <Segmented
              label={COPY.drawer.documents}
              size="small"
              options={tabs}
              {...(active === undefined ? {} : { active })}
              onChange={setActive}
            />
          )}
          {shown !== undefined && (
            <PaperCard>
              <h3 data-document-heading className="mb-[8px] font-legal text-[15px]">
                {DOCUMENT_HEADINGS[shown.purpose] ?? PURPOSES[shown.purpose]}
              </h3>
              <p className="text-meta text-ink-3">{COPY.drawer.separate}</p>
            </PaperCard>
          )}
        </div>
      )}
    </Sheet>
  );
}
