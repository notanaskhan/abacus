import {
  type EmailPreviewOut,
  type EmailTemplateRowOut,
  type FollowUpPolicyFields,
  type PortalSettingsDraftIn,
  type PortalSettingsOut,
  type SendingDomainOut,
  previewEmailTemplate,
} from "@abacus/api-client";
import {
  checkSendingDomainMutation,
  createSendingDomainMutation,
  discardPortalSettingsDraftMutation,
  getEmailTemplateOptions,
  getPortalSettingsQueryKey,
  getPortalSettingsOptions,
  listEmailTemplatesOptions,
  listSendingDomainsQueryKey,
  listSendingDomainsOptions,
  previewPortalOptions,
  publishEmailTemplateMutation,
  publishPortalSettingsMutation,
  revokeSendingDomainMutation,
  savePortalSettingsDraftMutation,
  testSendEmailTemplateMutation,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  Dialog,
  Drawer,
  EmptyState,
  ErrorState,
  Fieldset,
  FieldsetAdd,
  Icon,
  Picker,
  Pill,
  PortalBrandProvider,
  Segmented,
  SettingsLayout,
  Skeleton,
  ValueRow,
  date,
  time,
  toast,
  weekdayDate,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { useSession } from "../../app-core/session";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { EmailPreview } from "../../domain/communications";
import { PortalPreviewFrame, type PreviewDevice, previewBrand } from "../../domain/portal";
import { GROUPS } from "../ADM-01/copy";
import { PortalHomePreview } from "../POR-02";
import { COPY } from "./copy";

// ADM-10 · Portal branding & client experience (R-01-T28; R-01 §3.8, §5; docs/screens/ADM-10.md)
// on the T12 frame, section "Portal": the 520 form (Brand, Sender domain, Email templates,
// Reminders, Client experience) and the sticky 570 live preview (POR-02's home for the person
// previewed, in the firm app, inert) with the Reminder email card. Every artboard is a data
// condition of one screen:
//
//   a  published settings, preview as Claire Feld, Publish disabled
//   b  a draft (cadence 5): "Unsaved changes", Publish enabled, Next reminder Mon, Sep 21
//   c  the phone preview (`device=phone`)
//   d  the sender domain Pending DNS: its records, DMARC guidance and the neutral fallback lines
//   e  `?ov=email-template:reconnect_request`: the O2 480 editor drawer
//   f  after Publish: no draft, the toast
//   g  preview as Tess Moreno (an entity client: Approvals)
//
// An edit saves the draft at once (`PUT …/draft` with `expected_version`); Discard deletes it and
// Publish writes one insert-only version with a fresh second factor. What the viewer may do is the
// server's `allowed_actions` (the matrix), never a role comparison. Nothing inside the preview
// frame or the email card names the product while the footer is off (DEC-01, DEC-59).

export interface Adm10Search {
  as?: string | undefined;
  device?: string | undefined;
  ov?: string | undefined;
}

export interface PreviewContact {
  id: string;
  name: string;
}

export interface ADM10Props {
  search: Adm10Search;
  onSearch: (next: Adm10Search) => void;
  /** The contacts the viewer can see (DEC-20); empty: the sample client only. */
  previewAs?: readonly PreviewContact[];
  onNavigate?: (section: string) => void;
  onBack?: () => void;
  /** "Edit in POR-20 ›". */
  onOpenTemplate?: (key: string) => void;
  /** The preview frame, opened as POR-02 in a new tab (`/settings/portal/preview`). */
  onOpenPreview?: (as: string, device: PreviewDevice) => void;
}

const SAMPLE = "sample";
const TEMPLATE_OV = "email-template:";

type Problem = { detail?: unknown } | null | undefined;
const detailOf = (error: unknown): string | undefined => {
  const detail = (error as Problem)?.detail;
  return typeof detail === "string" ? detail : undefined;
};
const idempotency = (): { "Idempotency-Key": string } => ({
  "Idempotency-Key": crypto.randomUUID(),
});

/** "9:00 AM" from the policy's "09:00". */
function clock(hhmm: string): string {
  const [h = "9", m = "00"] = hhmm.split(":");
  const hour = Number(h);
  const suffix = hour >= 12 ? "PM" : "AM";
  return `${String(((hour + 11) % 12) + 1)}:${m} ${suffix}`;
}

/** "Mon, Sep 21": a reminder's day, in the firm's zone. */
function dayOf(iso: string, now: Date): string {
  const weekday = weekdayDate(iso, { now, tz: DEFAULT_TZ }).split(",")[0] ?? "";
  return `${weekday.slice(0, 3)}, ${date(iso, { now, tz: DEFAULT_TZ })}`;
}
const shiftDay = (day: string, now: Date): string => dayOf(`${day}T17:00:00Z`, now);

function draftIn(
  settings: PortalSettingsOut,
  policy: FollowUpPolicyFields,
): PortalSettingsDraftIn {
  const base = settings.draft ?? settings.published;
  const brand = settings.draft?.brand ?? {
    portal_name: settings.published?.brand.portal_name ?? "",
    sender_display_name: settings.published?.brand.sender_display_name ?? "",
    secured_footer: settings.published?.brand.secured_footer ?? false,
  };
  return {
    brand,
    client_experience: base?.client_experience ?? {},
    follow_up_policy: policy,
    expected_version: settings.draft?.expected_version ?? 0,
  };
}

function Card({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}): JSX.Element {
  return (
    <section aria-label={title} className="rounded-tile bg-card shadow-e1">
      <header className="flex h-[36px] items-center justify-between px-[12px]">
        <h3 className="text-section font-medium">{title}</h3>
        {action}
      </header>
      {children}
    </section>
  );
}

// --- the sender domain (d) ------------------------------------------------------------------------

function DomainStatus({ domain }: { domain: SendingDomainOut }): JSX.Element {
  if (domain.status === "verified") {
    return (
      <Pill variant="green-tint" check>
        {COPY.domain.verified}
      </Pill>
    );
  }
  if (domain.status === "pending_dns")
    return <Pill variant="amber">{COPY.domain.pendingDns}</Pill>;
  return <Pill variant="red-tint">{COPY.domain.failed}</Pill>;
}

function DomainRecords({
  domain,
  host,
  sender,
}: {
  domain: SendingDomainOut;
  host: string;
  sender: string;
}): JSX.Element {
  return (
    <div className="flex flex-col gap-[8px] px-[12px] pb-[10px] text-dense">
      <p className="text-ink-3">{COPY.domain.records}</p>
      <table className="w-full table-fixed text-meta">
        <thead className="text-ink-3">
          <tr>
            <th className="w-[54px] text-left font-normal">{COPY.domain.recordColumns.type}</th>
            <th className="text-left font-normal">{COPY.domain.recordColumns.name}</th>
            <th className="text-left font-normal">{COPY.domain.recordColumns.value}</th>
          </tr>
        </thead>
        <tbody>
          {domain.records.map((r) => (
            <tr key={`${r.type}:${r.name}:${r.value}`} className="align-top">
              <td className="py-[2px]">{r.type}</td>
              <td className="break-all py-[2px] font-mono">{r.name}</td>
              <td className="break-all py-[2px] font-mono">{r.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-ink-3">{COPY.domain.dmarc(domain.domain)}</p>
      <div className="flex flex-col gap-[2px] rounded-tile bg-nested px-[10px] py-[8px]">
        <p className="text-ink-3">{COPY.domain.fallback}</p>
        <p>{COPY.domain.fallbackHost(host)}</p>
        <p>{sender}</p>
      </div>
    </div>
  );
}

// --- the O2 template drawer (e) ----------------------------------------------------------------------

function TemplateDrawer({
  templateKey,
  onClose,
  onStepUp,
}: {
  templateKey: string;
  onClose: () => void;
  onStepUp: () => void;
}): JSX.Element {
  const queries = useQueryClient();
  const session = useSession();
  const path = { path: { key: templateKey } };
  const template = useQuery(getEmailTemplateOptions(path));
  const t = template.data;
  const source = t?.draft ? "draft" : "published";
  const preview = useQuery({
    queryKey: ["adm10-template-preview", templateKey, source, t?.draft?.expected_version ?? 0],
    enabled: t !== undefined && (t.draft !== null || t.published !== null),
    queryFn: async (): Promise<EmailPreviewOut> =>
      (await previewEmailTemplate({ ...path, body: { source, width: 390 }, throwOnError: true }))
        .data,
  });
  const failed = (error: unknown): void => {
    if (detailOf(error) === "forbidden") onStepUp();
    else toast.show(COPY.error.saveFailed);
  };
  const publish = useMutation({
    ...publishEmailTemplateMutation(),
    onSuccess: async () => {
      await queries.invalidateQueries({ queryKey: getEmailTemplateOptions(path).queryKey });
      await queries.invalidateQueries({ queryKey: listEmailTemplatesOptions().queryKey });
    },
    onError: failed,
  });
  const testSend = useMutation({
    ...testSendEmailTemplateMutation(),
    onSuccess: (sent) => {
      toast.show(COPY.toast.testSent(sent.sent_to));
    },
    onError: failed,
  });
  const name = t?.name ?? COPY.templates.rows[templateKey]?.[0] ?? templateKey;
  const actions = new Set(t?.allowed_actions ?? []);
  const current = t?.published?.version ?? 0;
  const content = t?.draft ?? t?.published;
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={name}
      width={480}
      {...(t?.published == null
        ? {}
        : { meta: <Pill variant="green-tint">{COPY.drawer.published(current)}</Pill> })}
      footer={
        <div className="flex justify-end gap-[8px]">
          {actions.has("test_send") && (
            <Button
              variant="secondary"
              onClick={() => {
                testSend.mutate({ ...path, body: {}, headers: idempotency() });
              }}
            >
              {COPY.drawer.sendTest(session.user?.email ?? "")}
            </Button>
          )}
          {actions.has("publish") && (
            <Button
              disabled={t?.draft == null}
              onClick={() => {
                publish.mutate({ ...path, headers: idempotency() });
              }}
            >
              {COPY.drawer.publish(current + 1)}
            </Button>
          )}
        </div>
      }
    >
      {template.isPending && <Skeleton />}
      {template.isError && <ErrorState title={COPY.error.load} />}
      {content != null && (
        <div className="flex flex-col gap-[10px]">
          <Fieldset title={COPY.drawer.email} flush>
            <ValueRow kind="value" label={COPY.drawer.subject}>
              {content.subject}
            </ValueRow>
            <ValueRow kind="info" label={COPY.drawer.body}>
              <div className="flex flex-col gap-[4px] py-[6px] text-dense">
                {content.blocks.map((b) => (
                  <p key={b.id}>{b.text}</p>
                ))}
              </div>
            </ValueRow>
            {content.cta_label != null && (
              <ValueRow kind="value" label={COPY.drawer.button}>
                {content.cta_label}
              </ValueRow>
            )}
          </Fieldset>
          <Fieldset title={COPY.drawer.variables} flush>
            <p className="px-[12px] py-[6px] text-meta text-ink-3">{COPY.drawer.variablesHelp}</p>
            <div className="flex flex-wrap gap-[4px] px-[12px] pb-[8px]">
              {(t?.variables ?? []).map((v) => (
                <Pill key={v.name} variant="tag">{`{${v.name}}`}</Pill>
              ))}
            </div>
          </Fieldset>
          <Fieldset title={COPY.drawer.preview} flush>
            {preview.data === undefined ? (
              <Skeleton />
            ) : (
              <EmailPreview
                html={preview.data.html}
                text={preview.data.text}
                width="390"
                title={name}
                showText="Plain text"
                hideText="Hide plain text"
              />
            )}
          </Fieldset>
        </div>
      )}
    </Drawer>
  );
}

// --- the screen -----------------------------------------------------------------------------------

export function ADM10({
  search,
  onSearch,
  previewAs = [],
  onNavigate,
  onBack,
  onOpenTemplate,
  onOpenPreview,
}: ADM10Props): JSX.Element {
  const queries = useQueryClient();
  const now = useNow();
  const editorOn = useFlag("portal.settings_editor");
  const senderOn = useFlag("communications.firm_sender_domain");
  const settings = useQuery(getPortalSettingsOptions());
  const domains = useQuery(listSendingDomainsOptions());
  const templates = useQuery(listEmailTemplatesOptions());
  const as = search.as ?? previewAs[0]?.id ?? SAMPLE;
  const device: PreviewDevice = search.device === "phone" ? "phone" : "desktop";
  const preview = useQuery({
    ...previewPortalOptions({ query: { as, device } }),
    retry: false,
  });
  const reminder = useQuery({
    queryKey: ["adm10-reminder-email", as],
    queryFn: async (): Promise<EmailPreviewOut> =>
      (
        await previewEmailTemplate({
          path: { key: "reminder" },
          body: {
            source: "published",
            width: 600,
            ...(as === SAMPLE ? {} : { sample_contact_id: as }),
          },
          throwOnError: true,
        })
      ).data,
    retry: false,
  });
  const [stepUp, setStepUp] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newDomain, setNewDomain] = useState("");

  const refresh = async (): Promise<void> => {
    await queries.invalidateQueries({ queryKey: getPortalSettingsQueryKey() });
    await queries.invalidateQueries({ queryKey: ["previewPortal"] });
  };
  const failed = (error: unknown): void => {
    const detail = detailOf(error);
    if (detail === "forbidden") setStepUp(true);
    else if (detail === "stale_version") toast.show(COPY.error.staleDraft);
    else if (detail === "sending_domain_exists") toast.show(COPY.domain.exists);
    else if (detail === "sending_domain_unavailable") toast.show(COPY.domain.unavailable);
    else toast.show(COPY.error.saveFailed);
    void refresh();
  };
  const save = useMutation({
    ...savePortalSettingsDraftMutation(),
    onSuccess: refresh,
    onError: failed,
  });
  const discard = useMutation({
    ...discardPortalSettingsDraftMutation(),
    onSuccess: refresh,
    onError: failed,
  });
  const publish = useMutation({
    ...publishPortalSettingsMutation(),
    onSuccess: async () => {
      toast.show(COPY.toast.published);
      await refresh();
    },
    onError: failed,
  });
  const domainsChanged = async (): Promise<void> => {
    await queries.invalidateQueries({ queryKey: listSendingDomainsQueryKey() });
    await queries.invalidateQueries({ queryKey: ["adm10-reminder-email"] });
  };
  const addDomain = useMutation({
    ...createSendingDomainMutation(),
    onSuccess: async () => {
      setAdding(false);
      setNewDomain("");
      toast.show(COPY.toast.domainAdded);
      await domainsChanged();
    },
    onError: failed,
  });
  const checkDomain = useMutation({
    ...checkSendingDomainMutation(),
    onSuccess: domainsChanged,
    onError: failed,
  });
  const removeDomain = useMutation({
    ...revokeSendingDomainMutation(),
    onSuccess: async () => {
      toast.show(COPY.toast.domainRemoved);
      await domainsChanged();
    },
    onError: failed,
  });

  const s = settings.data;
  const actions = new Set(s?.allowed_actions ?? []);
  const canEdit = editorOn && actions.has("edit");
  const canPublish = editorOn && actions.has("publish");
  const readOnly = s !== undefined && !actions.has("edit");
  const values = s?.draft ?? s?.published;
  const brand = s?.published?.brand;
  const policy = s?.draft?.follow_up_policy ?? s?.published?.follow_up_policy;
  const experience = values?.client_experience;
  const dirty = s?.draft != null;
  const domain = (domains.data?.items ?? []).find((d) => d.status !== "revoked");
  const display = s?.draft?.brand.sender_display_name ?? brand?.sender_display_name ?? "";
  const verified = domain?.status === "verified" && senderOn;
  const neutralSender = reminder.data?.from_address ?? "";
  const senderLine = verified
    ? COPY.sender.address(display, `${domain.from_local_part}@${domain.domain}`)
    : COPY.sender.address(display, neutralSender);
  const host = brand?.portal_host ?? "";

  const editPolicy = (patch: Partial<FollowUpPolicyFields>): void => {
    if (s === undefined || policy === undefined || !canEdit) return;
    save.mutate({ body: draftIn(s, { ...policy, ...patch }) });
  };
  const setSearch = (patch: Partial<Adm10Search>): void => {
    onSearch({ ...search, ...patch });
  };

  const rows: readonly EmailTemplateRowOut[] = templates.data?.items ?? [];
  const designed = rows.filter((r) => r.group === "designed");
  const publishedCount = designed.filter((r) => r.published != null).length;
  const draftCount = designed.filter((r) => r.draft != null).length;
  const previewName =
    as === SAMPLE
      ? COPY.preview.sample
      : (previewAs.find((c) => c.id === as)?.name ?? COPY.preview.sample);
  const next = s?.next_reminder;
  const templateKey = search.ov?.startsWith(TEMPLATE_OV)
    ? search.ov.slice(TEMPLATE_OV.length)
    : null;

  const form = (
    <div className="flex w-[520px] flex-none flex-col gap-[12px]">
      {!editorOn && s !== undefined && (
        <p role="note" className="rounded-tile bg-nested px-[12px] py-[8px] text-dense text-ink-3">
          {COPY.flagOff.note}
        </p>
      )}
      <Fieldset title={COPY.brand.title} flush>
        <ValueRow kind="value" label={COPY.brand.logo} readOnly={!canEdit}>
          {brand?.logo_url == null ? COPY.brand.noLogo : COPY.brand.replace}
        </ValueRow>
        <ValueRow kind="value" label={COPY.brand.portalName} readOnly={!canEdit}>
          {s?.draft?.brand.portal_name ?? brand?.portal_name ?? ""}
        </ValueRow>
        <ValueRow kind="value" label={COPY.brand.accent} help={COPY.brand.accentHelp} lock>
          {COPY.brand.espresso}
        </ValueRow>
        <ValueRow
          kind="value"
          label={COPY.brand.portalHost}
          help={COPY.brand.customDomainLater}
          lock
        >
          {host}
        </ValueRow>
        <ValueRow
          kind="value"
          label={COPY.brand.sender}
          {...(verified || domain === undefined
            ? {}
            : { help: COPY.sender.replyTo(`${domain.from_local_part}@${domain.domain}`) })}
        >
          {senderLine}
        </ValueRow>
        <ValueRow
          kind="toggle"
          label={COPY.brand.securedFooter}
          checked={s?.draft?.brand.secured_footer ?? brand?.secured_footer ?? false}
          disabled={!canEdit}
          readOnly={!canEdit}
          onChange={(checked) => {
            if (s === undefined || policy === undefined) return;
            const body = draftIn(s, policy);
            save.mutate({ body: { ...body, brand: { ...body.brand, secured_footer: checked } } });
          }}
        />
      </Fieldset>

      <Fieldset
        title={COPY.domain.title}
        flush
        {...(domain === undefined && senderOn && actions.has("edit")
          ? {
              action: (
                <FieldsetAdd
                  onClick={() => {
                    setAdding(true);
                  }}
                >
                  {COPY.domain.add}
                </FieldsetAdd>
              ),
            }
          : {})}
      >
        {domains.isPending && <Skeleton />}
        {domain === undefined && !domains.isPending && (
          <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.domain.none}</p>
        )}
        {domain !== undefined && (
          <>
            <ValueRow kind="value" label={domain.domain}>
              <span className="flex items-center gap-[6px]">
                <DomainStatus domain={domain} />
                {senderOn && actions.has("edit") && domain.status !== "verified" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      checkDomain.mutate({ path: { domain_id: domain.id } });
                    }}
                  >
                    {COPY.domain.check}
                  </Button>
                )}
                {senderOn && actions.has("edit") && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      removeDomain.mutate({ path: { domain_id: domain.id } });
                    }}
                  >
                    {COPY.domain.remove}
                  </Button>
                )}
              </span>
            </ValueRow>
            {domain.status === "failed" && domain.failure_reason != null && (
              <p role="status" className="px-[12px] pb-[8px] text-dense text-red-ink">
                {COPY.domain.failedReason[domain.failure_reason] ?? ""}
              </p>
            )}
            {domain.status !== "verified" && (
              <DomainRecords
                domain={domain}
                host={host}
                sender={COPY.domain.fallbackSender(display, neutralSender)}
              />
            )}
          </>
        )}
      </Fieldset>

      <Fieldset title={COPY.templates.title} flush>
        <p className="px-[12px] py-[6px] text-meta text-ink-3">{COPY.templates.help}</p>
        <ul aria-label={COPY.templates.title} className="flex flex-col">
          {designed.map((row) => {
            const [label, used] = COPY.templates.rows[row.key] ?? [row.name, row.used_by_label];
            return (
              <li key={row.key}>
                <button
                  type="button"
                  className="flex min-h-[40px] w-full items-center gap-[10px] px-[12px] text-left text-body hover:bg-hover"
                  onClick={() => {
                    setSearch({ ov: `${TEMPLATE_OV}${row.key}` });
                  }}
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-medium">{label}</span>
                    <span className="truncate text-meta text-ink-3">{used}</span>
                  </span>
                  {row.published != null && (
                    <Pill variant="green-tint">
                      {COPY.templates.published(row.published.version)}
                    </Pill>
                  )}
                  {row.draft != null && (
                    <Pill variant="amber">{COPY.templates.draft(row.draft.version)}</Pill>
                  )}
                  <Icon name="chevron-right" size={13} />
                </button>
              </li>
            );
          })}
        </ul>
        {designed.length > 0 && (
          <p className="px-[12px] py-[6px] text-meta text-ink-3">
            {COPY.templates.footer(publishedCount, designed.length, draftCount)}
          </p>
        )}
      </Fieldset>

      {policy !== undefined && (
        <Fieldset title={COPY.reminders.title} flush>
          <ValueRow
            kind="select"
            label={COPY.reminders.cadence}
            value={String(policy.cadence_days ?? 7)}
            options={[3, 5, 7, 10, 14].map((n) => ({
              value: String(n),
              label: COPY.reminders.cadenceValue(n),
            }))}
            readOnly={!canEdit}
            onChange={(value) => {
              editPolicy({ cadence_days: Number(value) });
            }}
          />
          <ValueRow
            kind="select"
            label={COPY.reminders.max}
            value={String(policy.max_reminders ?? 4)}
            options={[1, 2, 3, 4].map((n) => ({
              value: String(n),
              label: COPY.reminders.maxValue(n),
            }))}
            readOnly={!canEdit}
            onChange={(value) => {
              editPolicy({ max_reminders: Number(value) });
            }}
          />
          <ValueRow kind="value" label={COPY.reminders.sendAt} readOnly={!canEdit}>
            {COPY.reminders.sendAtValue(
              clock(policy.send_local_time ?? "09:00"),
              policy.weekdays_only ?? true,
            )}
          </ValueRow>
          <ValueRow
            kind="toggle"
            label={COPY.reminders.stopWhenDone}
            checked={policy.stop_on_binder_done ?? true}
            disabled={!canEdit}
            readOnly={!canEdit}
            onChange={(checked) => {
              editPolicy({ stop_on_binder_done: checked });
            }}
          />
          <ValueRow
            kind="toggle"
            label={COPY.reminders.drafted}
            help={COPY.reminders.help}
            checked={(policy.mode ?? "draft_for_person") === "draft_for_person"}
            disabled
            readOnly
          />
        </Fieldset>
      )}

      {experience !== undefined && (
        <Fieldset title={COPY.experience.title} flush>
          {(
            [
              ["allow_upload_something_else", COPY.experience.uploadElse],
              ["phone_capture", COPY.experience.phoneCapture],
              ["show_team_card", COPY.experience.teamCard],
              ["show_progress_per_item", COPY.experience.progress],
            ] as const
          ).map(([field, label]) => (
            <ValueRow
              key={field}
              kind="toggle"
              label={label}
              checked={experience[field] ?? false}
              disabled={!canEdit}
              readOnly={!canEdit}
              onChange={(checked) => {
                if (s === undefined || policy === undefined) return;
                const body = draftIn(s, policy);
                save.mutate({
                  body: {
                    ...body,
                    client_experience: { ...body.client_experience, [field]: checked },
                  },
                });
              }}
            />
          ))}
        </Fieldset>
      )}
    </div>
  );

  const previewColumn = (
    <aside className="sticky top-[12px] flex w-[570px] flex-none flex-col gap-[10px]">
      <Card
        title={COPY.preview.title}
        action={
          <span className="flex items-center gap-[8px]">
            <Segmented
              size="small"
              label={COPY.preview.title}
              options={[COPY.preview.desktop, COPY.preview.phone]}
              active={device === "phone" ? COPY.preview.phone : COPY.preview.desktop}
              onChange={(label) => {
                setSearch({ device: label === COPY.preview.phone ? "phone" : "desktop" });
              }}
            />
            <Picker
              label={COPY.preview.as}
              value={as}
              options={[
                ...previewAs.map((c) => ({ value: c.id, label: COPY.preview.asName(c.name) })),
                { value: SAMPLE, label: COPY.preview.sample },
              ]}
              onChange={(value) => {
                setSearch({ as: value });
              }}
            />
          </span>
        }
      >
        <div className="px-[12px] pb-[12px]">
          {preview.isPending && <Skeleton />}
          {preview.isError &&
            (detailOf(preview.error) === "not_found" ? (
              <EmptyState title={COPY.preview.notFound} />
            ) : (
              <ErrorState title={COPY.preview.error} />
            ))}
          {preview.data !== undefined && (
            <button
              type="button"
              className="block w-full text-left"
              aria-label={COPY.preview.openFor(previewName)}
              onClick={() => {
                onOpenPreview?.(as, device);
              }}
            >
              <PortalPreviewFrame
                brand={preview.data.brand}
                device={device}
                label={COPY.preview.label(previewName)}
              >
                <PortalHomePreview
                  home={preview.data.home}
                  user={previewName}
                  mobile={device === "phone"}
                />
              </PortalPreviewFrame>
            </button>
          )}
        </div>
      </Card>
      <Card
        title={COPY.emailCard.title}
        action={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onOpenTemplate?.("reminder");
            }}
          >
            {COPY.emailCard.edit}
          </Button>
        }
      >
        <dl className="grid grid-cols-[96px_1fr] gap-x-[10px] gap-y-[2px] px-[12px] text-dense">
          <dt className="text-ink-3">{COPY.emailCard.from}</dt>
          <dd>{senderLine}</dd>
          {next?.last_sent_at != null && (
            <>
              <dt className="text-ink-3">{COPY.emailCard.lastReminder}</dt>
              <dd>{`${dayOf(next.last_sent_at, now)}, ${time(next.last_sent_at, { tz: DEFAULT_TZ })}`}</dd>
            </>
          )}
        </dl>
        {next != null && (
          <div className="flex flex-col px-[12px] pt-[6px] text-dense">
            <p className="font-medium">{COPY.emailCard.next(dayOf(next.next_send_at, now))}</p>
            {next.shifted_from != null && (
              <p className="text-amber-ink">
                {COPY.emailCard.shift(shiftDay(next.shifted_from, now))}
              </p>
            )}
          </div>
        )}
        <div className="px-[12px] py-[10px]">
          {reminder.data === undefined ? (
            reminder.isError ? null : (
              <Skeleton />
            )
          ) : (
            <EmailPreview
              html={reminder.data.html}
              text={reminder.data.text}
              width="600"
              title={COPY.emailCard.title}
              showText="Plain text"
              hideText="Hide plain text"
            />
          )}
          <p className="pt-[6px] text-meta text-ink-3">{COPY.emailCard.sentFrom(display, host)}</p>
        </div>
      </Card>
    </aside>
  );

  return (
    <SettingsLayout
      bare
      wide
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.header.title}
      backLabel={COPY.header.back}
      {...(onBack === undefined ? {} : { onBack })}
      navTitle={COPY.header.navTitle}
      groups={GROUPS.map((g) => ({
        ...g,
        sections: g.sections.filter(
          (section) =>
            ["general", "people", "offices", "security", "audit-log", "portal"].includes(
              section.id,
            ) || PLANNED_VISIBLE,
        ),
      })).filter((g) => g.sections.length > 0)}
      active="portal"
      onSelect={(id) => {
        if (id !== "portal") onNavigate?.(id);
      }}
      dirty={dirty}
      readOnly={readOnly}
      readOnlyText={COPY.readOnly}
      headerActions={
        <span className="flex items-center gap-[8px]">
          {dirty && <span className="text-dense text-amber-ink">{COPY.header.unsaved}</span>}
          {canEdit && (
            <Button
              variant="secondary"
              size="sm"
              disabled={!dirty}
              onClick={() => {
                discard.mutate({});
              }}
            >
              {COPY.header.discard}
            </Button>
          )}
          {canPublish && (
            <Button
              size="sm"
              disabled={!dirty || publish.isPending}
              onClick={() => {
                publish.mutate({ headers: idempotency() });
              }}
            >
              {COPY.header.publish}
            </Button>
          )}
        </span>
      }
      overlay={
        <>
          {templateKey !== null && (
            <TemplateDrawer
              templateKey={templateKey}
              onClose={() => {
                setSearch({ ov: undefined });
              }}
              onStepUp={() => {
                setStepUp(true);
              }}
            />
          )}
          <Dialog
            open={adding}
            onOpenChange={setAdding}
            title={COPY.domain.addTitle}
            description={COPY.domain.addHelp}
          >
            <form
              className="flex flex-col gap-[10px]"
              onSubmit={(event) => {
                event.preventDefault();
                addDomain.mutate({
                  body: { domain: newDomain.trim().toLowerCase(), from_local_part: "clients" },
                  headers: idempotency(),
                });
              }}
            >
              <ValueRow
                kind="text"
                label={COPY.domain.addLabel}
                value={newDomain}
                placeholder="Required"
                onChange={setNewDomain}
              />
              <div className="flex justify-end">
                <Button type="submit" disabled={newDomain.trim() === "" || addDomain.isPending}>
                  {COPY.domain.addConfirm}
                </Button>
              </div>
            </form>
          </Dialog>
        </>
      }
      stepUp={
        <Dialog
          open={stepUp}
          onOpenChange={setStepUp}
          title={COPY.stepUp.title}
          description={COPY.stepUp.body}
        >
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setStepUp(false);
              }}
            >
              {COPY.stepUp.cancel}
            </Button>
            <Button
              onClick={() => {
                signIn(currentRoute(), { forceLogin: true });
              }}
            >
              {COPY.stepUp.signIn}
            </Button>
          </div>
        </Dialog>
      }
    >
      {settings.isPending && <Skeleton />}
      {settings.isError && (
        <ErrorState
          title={COPY.error.load}
          onRetry={() => {
            void settings.refetch();
          }}
        />
      )}
      {s !== undefined && (
        <div className="flex items-start gap-[12px] px-[12px] pt-[12px] pb-[24px]">
          {form}
          {previewColumn}
        </div>
      )}
    </SettingsLayout>
  );
}

/** The preview in its own tab (`/settings/portal/preview?as=&device=`): POR-02 at full size, read
 * only, in the firm app (R-01 §5.1). Nothing in it navigates or writes. */
export function ADM10Preview({
  as,
  device,
  previewAs = [],
}: {
  as: string;
  device: PreviewDevice;
  previewAs?: readonly PreviewContact[];
}): JSX.Element {
  const preview = useQuery({ ...previewPortalOptions({ query: { as, device } }), retry: false });
  const name = previewAs.find((c) => c.id === as)?.name ?? COPY.preview.sample;
  if (preview.isError) {
    return detailOf(preview.error) === "not_found" ? (
      <EmptyState title={COPY.preview.notFound} />
    ) : (
      <ErrorState title={COPY.preview.error} />
    );
  }
  if (preview.data === undefined) return <Skeleton />;
  return (
    <figure
      aria-label={COPY.preview.label(name)}
      className="m-0 flex min-h-0 flex-1 justify-center"
    >
      <div inert className="flex min-h-0 flex-1 flex-col">
        <PortalBrandProvider brand={previewBrand(preview.data.brand)}>
          <PortalHomePreview home={preview.data.home} user={name} mobile={device === "phone"} />
        </PortalBrandProvider>
      </div>
    </figure>
  );
}
