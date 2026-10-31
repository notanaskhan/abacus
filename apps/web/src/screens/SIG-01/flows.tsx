import {
  type EnvelopeListRow,
  type ImportRecordIn,
  type ImportSignerIn,
  importEnvelopeRecord,
  previewEmailTemplate,
  recordWetSignature,
  remindEnvelopesPreview,
  stageEnvelopeImportFile,
} from "@abacus/api-client";
import {
  envelopeSummaryQueryKey,
  getEmailTemplateOptions,
  listClientsOptions,
  listContactsOptions,
  listEnvelopesQueryKey,
  remindEnvelopesSendMutation,
} from "@abacus/api-client/query";
import {
  type Actor,
  Button,
  Checkbox,
  Dialog,
  Fieldset,
  HumanAction,
  Label,
  SheetModal,
  ValueRow,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

// SIG-01's two flows (N-02-T15; docs/screens/SIG-01.md f and r; DEC-1057). Both are a person's
// act (INV-1): the reminder preview renders the firm's published `signature_reminder` template
// and the server's count, and nothing goes until the person clicks Send; Import signed package
// stages each file (scanned before storage) and imports once, attested (DF-12).

export const REMINDER_TEMPLATE = "signature_reminder";

/** The signers a reminder would reach on a row: those not yet signed. */
function waiting(row: EnvelopeListRow): string {
  return (row.signer_chips ?? [])
    .filter((c) => !c.signed)
    .map((c) => c.name)
    .join(" · ");
}

export function RemindDialog({
  rows,
  viewer,
  onClose,
}: {
  rows: readonly EnvelopeListRow[];
  viewer: Actor;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const open = rows.length > 0;
  const ids = rows.map((r) => r.id);
  const template = useQuery({
    ...getEmailTemplateOptions({ path: { key: REMINDER_TEMPLATE } }),
    enabled: open,
  });
  const version = template.data?.published?.version ?? null;
  const rendered = useQuery({
    queryKey: ["sig01", "reminder-render", version],
    enabled: open && version !== null,
    queryFn: async () =>
      (
        await previewEmailTemplate({
          path: { key: REMINDER_TEMPLATE },
          body: { source: "published", width: 600 },
          throwOnError: true,
        })
      ).data,
  });
  const counted = useQuery({
    queryKey: ["sig01", "reminder-count", ids, version],
    enabled: open && version !== null,
    queryFn: async () =>
      (
        await remindEnvelopesPreview({
          body: { envelope_ids: ids, template_version: version },
          throwOnError: true,
        })
      ).data,
  });
  const send = useMutation({
    ...remindEnvelopesSendMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: listEnvelopesQueryKey() });
      onClose();
    },
  });
  const n = counted.data?.count ?? rows.length;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.reminder.title}
      action={
        <HumanAction
          verb="Send"
          object={COPY.reminder.object(n)}
          actor={viewer}
          variant="primary"
          size="sm"
          disabled={version === null || counted.isPending || send.isPending}
          onClick={() => {
            if (version === null) return;
            send.mutate({
              body: { envelope_ids: ids, template_version: version },
              headers: { "Idempotency-Key": crypto.randomUUID() },
            });
          }}
        />
      }
    >
      <ul className="flex flex-col gap-[6px] text-body" aria-label={COPY.reminder.recipients}>
        {rows.map((r) => (
          <li key={r.id} className="flex flex-col">
            <span className="font-medium">{`${r.number} · ${r.title}`}</span>
            <span className="text-meta text-ink-3">{waiting(r)}</span>
          </li>
        ))}
      </ul>
      {template.isError && <p className="mt-[12px] text-body text-ink-2">{COPY.reminder.none}</p>}
      {rendered.data !== undefined && (
        <section
          aria-label={COPY.reminder.preview}
          className="mt-[12px] rounded-tile bg-nested p-[12px]"
        >
          <p className="text-meta text-ink-3">{`${template.data?.name ?? ""} · ${rendered.data.from_display}`}</p>
          <p className="mt-[4px] font-medium">{rendered.data.subject}</p>
          <p className="mt-[6px] whitespace-pre-line text-body text-ink-2">{rendered.data.text}</p>
        </section>
      )}
    </Dialog>
  );
}

const PURPOSES: readonly { code: ImportRecordIn["purpose"]; label: string }[] = [
  { code: "engagement_letter", label: COPY.importSheet.purposes.engagementLetter },
  { code: "form_8879", label: "Form 8879" },
  { code: "form_8879_pe", label: "Form 8879-PE" },
  { code: "form_8879_f", label: "Form 8879-F" },
  { code: "form_2848", label: "Form 2848" },
  { code: "form_8821", label: "Form 8821" },
  { code: "consent_7216", label: COPY.importSheet.purposes.consent },
  { code: "other", label: COPY.importSheet.purposes.other },
];
const METHODS: readonly { code: ImportSignerIn["identity_method"]; label: string }[] = [
  { code: "kba", label: COPY.importSheet.methods.kba },
  { code: "email_code", label: COPY.importSheet.methods.emailCode },
  { code: "in_person_id", label: COPY.importSheet.methods.inPerson },
  { code: "firm_sso", label: COPY.importSheet.methods.firmSso },
];
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

interface SignerRow {
  contactId: string;
  signedOn: string;
  method: ImportSignerIn["identity_method"];
}

const blankSigner = (): SignerRow => ({ contactId: "", signedOn: "", method: "kba" });

export function ImportSheet({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [clientId, setClientId] = useState("");
  const [title, setTitle] = useState("");
  const [purpose, setPurpose] = useState<ImportRecordIn["purpose"]>("engagement_letter");
  const [providerName, setProviderName] = useState("");
  const [signers, setSigners] = useState<SignerRow[]>([blankSigner()]);
  const [document, setDocument] = useState<File | null>(null);
  const [certificate, setCertificate] = useState<File | null>(null);
  const [attested, setAttested] = useState(false);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const clients = useQuery({ ...listClientsOptions({ query: { limit: 100 } }), enabled: open });
  const contacts = useQuery({
    ...listContactsOptions({ path: { client_id: clientId } }),
    enabled: open && clientId !== "",
  });
  const ready =
    clientId !== "" &&
    title.trim() !== "" &&
    providerName.trim() !== "" &&
    document !== null &&
    attested &&
    signers.every((s) => s.contactId !== "" && ISO_DAY.test(s.signedOn));

  const stage = async (file: File): Promise<string> => {
    const { data } = await stageEnvelopeImportFile({
      query: { filename: file.name, client_id: clientId },
      body: file as never,
      bodySerializer: null,
      headers: { "Content-Type": file.type || "application/octet-stream" },
      throwOnError: true,
    });
    return data.id;
  };

  const submit = async (): Promise<void> => {
    if (!ready) return;
    setBusy(true);
    setFailed(false);
    try {
      const uploads = [await stage(document)];
      if (certificate !== null) uploads.push(await stage(certificate));
      await importEnvelopeRecord({
        body: {
          purpose,
          client_id: clientId,
          title: title.trim(),
          provider_name: providerName.trim(),
          signers: signers.map((s) => ({
            contact_id: s.contactId,
            signed_on: s.signedOn,
            identity_method: s.method,
          })),
          upload_ids: uploads,
          attested: true,
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
        throwOnError: true,
      });
      void queryClient.invalidateQueries({ queryKey: listEnvelopesQueryKey() });
      void queryClient.invalidateQueries({ queryKey: envelopeSummaryQueryKey() });
      onClose();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <SheetModal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.importSheet.title}
      dirty={title !== "" || document !== null}
      footer={
        <Button
          variant="primary"
          size="sm"
          disabled={!ready || busy}
          onClick={() => {
            void submit();
          }}
        >
          {COPY.importSheet.import}
        </Button>
      }
    >
      <div className="flex flex-col gap-[12px] p-[16px] text-body">
        <Fieldset flush>
          <ValueRow
            kind="select"
            label={COPY.importSheet.client}
            value={clientId}
            placeholder={COPY.importSheet.required}
            options={(clients.data?.items ?? []).map((c) => ({ value: c.id, label: c.name }))}
            onChange={(next) => {
              setClientId(next);
              setSigners([blankSigner()]);
            }}
          />
          <ValueRow
            kind="select"
            label={COPY.importSheet.purpose}
            value={purpose}
            options={PURPOSES.map((p) => ({ value: p.code, label: p.label }))}
            onChange={(next) => {
              setPurpose(next as ImportRecordIn["purpose"]);
            }}
          />
          <ValueRow
            kind="text"
            label={COPY.importSheet.titleField}
            placeholder={COPY.importSheet.required}
            value={title}
            onChange={setTitle}
          />
          <ValueRow
            kind="text"
            label={COPY.importSheet.provider}
            placeholder={COPY.importSheet.required}
            value={providerName}
            onChange={setProviderName}
          />
        </Fieldset>
        {signers.map((s, i) => (
          <Fieldset key={i} title={COPY.importSheet.signerN(i + 1)} flush>
            <ValueRow
              kind="select"
              label={COPY.importSheet.signer}
              value={s.contactId}
              placeholder={COPY.importSheet.required}
              options={(contacts.data?.items ?? []).map((c) => ({ value: c.id, label: c.name }))}
              onChange={(next) => {
                setSigners(signers.map((x, j) => (j === i ? { ...x, contactId: next } : x)));
              }}
            />
            <ValueRow
              kind="text"
              label={COPY.importSheet.signedOn}
              placeholder={COPY.importSheet.dayFormat}
              value={s.signedOn}
              onChange={(next) => {
                setSigners(signers.map((x, j) => (j === i ? { ...x, signedOn: next } : x)));
              }}
            />
            <ValueRow
              kind="select"
              label={COPY.importSheet.method}
              value={s.method}
              options={METHODS.map((m) => ({ value: m.code, label: m.label }))}
              onChange={(next) => {
                const method = next as ImportSignerIn["identity_method"];
                setSigners(signers.map((x, j) => (j === i ? { ...x, method } : x)));
              }}
            />
          </Fieldset>
        ))}
        <Button
          variant="secondary"
          size="sm"
          disabled={signers.length >= 20}
          onClick={() => {
            setSigners([...signers, blankSigner()]);
          }}
        >
          {COPY.importSheet.addSigner}
        </Button>
        <Label htmlFor="sig01-document">{COPY.importSheet.document}</Label>
        <input
          id="sig01-document"
          type="file"
          accept="application/pdf"
          onChange={(e) => {
            setDocument(e.target.files?.[0] ?? null);
          }}
        />
        <Label htmlFor="sig01-certificate">{COPY.importSheet.certificate}</Label>
        <input
          id="sig01-certificate"
          type="file"
          accept="application/pdf"
          onChange={(e) => {
            setCertificate(e.target.files?.[0] ?? null);
          }}
        />
        <Checkbox
          label={COPY.importSheet.attest}
          showLabel
          checked={attested}
          onChange={setAttested}
        />
        {failed && <p className="text-body text-red-ink">{COPY.importSheet.failed}</p>}
      </div>
    </SheetModal>
  );
}

/** DF-11 (N-02-T27): the hand-signed form for a signer whose identity checks failed. The scan is
 * staged first (scanned before storage), then recorded once, attested, by the person. */
export function WetSignatureSheet({
  open,
  row,
  signerId,
  signerName,
  onClose,
}: {
  open: boolean;
  row: EnvelopeListRow;
  signerId: string;
  signerName: string;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [scan, setScan] = useState<File | null>(null);
  const [signedOn, setSignedOn] = useState("");
  const [receivedOn, setReceivedOn] = useState("");
  const [attested, setAttested] = useState(false);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const ready =
    scan !== null &&
    attested &&
    ISO_DAY.test(signedOn) &&
    (receivedOn === "" || ISO_DAY.test(receivedOn));

  const submit = async (): Promise<void> => {
    if (!ready) return;
    setBusy(true);
    setFailed(false);
    try {
      const { data } = await stageEnvelopeImportFile({
        query: { filename: scan.name, client_id: row.client_id },
        body: scan as never,
        bodySerializer: null,
        headers: { "Content-Type": scan.type || "application/octet-stream" },
        throwOnError: true,
      });
      await recordWetSignature({
        path: { envelope_id: row.id, signer_id: signerId },
        body: {
          upload_id: data.id,
          signed_on: signedOn,
          attested: true,
          received_on: receivedOn === "" ? null : receivedOn,
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
        throwOnError: true,
      });
      void queryClient.invalidateQueries({ queryKey: listEnvelopesQueryKey() });
      void queryClient.invalidateQueries({ queryKey: envelopeSummaryQueryKey() });
      onClose();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <SheetModal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.df11.sheetTitle(signerName)}
      dirty={scan !== null || signedOn !== ""}
      footer={
        <Button
          variant="primary"
          size="sm"
          disabled={!ready || busy}
          onClick={() => {
            void submit();
          }}
        >
          {COPY.df11.record}
        </Button>
      }
    >
      <div className="flex flex-col gap-[12px] p-[16px] text-body">
        <Label htmlFor="sig01-wet-scan">{COPY.df11.scan}</Label>
        <input
          id="sig01-wet-scan"
          type="file"
          accept="application/pdf,image/png,image/jpeg"
          onChange={(e) => {
            setScan(e.target.files?.[0] ?? null);
          }}
        />
        <Fieldset flush>
          <ValueRow
            kind="text"
            label={COPY.df11.signedOn}
            placeholder={COPY.importSheet.dayFormat}
            value={signedOn}
            onChange={setSignedOn}
          />
          <ValueRow
            kind="text"
            label={COPY.df11.receivedOn}
            placeholder={COPY.importSheet.dayFormat}
            value={receivedOn}
            onChange={setReceivedOn}
          />
        </Fieldset>
        <Checkbox label={COPY.df11.attest} showLabel checked={attested} onChange={setAttested} />
        {failed && <p className="text-body text-red-ink">{COPY.df11.failed}</p>}
      </div>
    </SheetModal>
  );
}
