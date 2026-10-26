import type {
  FirmOfficeOut,
  GlanceRowOut,
  SettingValueOut,
  SettingsSectionValuesOut,
} from "@abacus/api-client";
import {
  firmMembersOptions,
  officesOptions,
  settingsOverviewOptions,
  settingsOverviewQueryKey,
  settingsSectionOptions,
  settingsSectionQueryKey,
  updateSettingsSectionMutation,
} from "@abacus/api-client/query";
import {
  Button,
  ConfirmDialog,
  Dialog,
  EmptyState,
  Fieldset,
  FieldsetAdd,
  FirmMark,
  SettingsLayout,
  SettingsLock,
  StatusDisc,
  Icon,
  ValueRow,
  date,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { COPY, GLANCE, GROUPS } from "./copy";

// ADM-01 · Settings home & firm profile (G-01-T07; G-01 §3.1–3.2) on the T12 frame. The screen is
// its data: the overview names the sections the viewer may read and the At a glance rows whose
// owners registered a provider; each section answers its keys, `version` and whether the viewer may
// write. Every artboard is a state of the same form:
//
//   a  Grace Holloway, clean: Save disabled
//   b  a change (time zone CT → ET): "Unsaved changes", Discard and Save
//   c  Display name emptied: "Required" in brick with its helper; Save blocked
//   d  Daniel Reyes (partner): the amber banner, locks on the bands, no Save; At a glance stays
//   e  Felix Andersen (security admin): read-only, no Plan & seats, Security first in At a glance
//   f  saved: the toast "Firm settings saved"
//
// Saving sends `PATCH /v1/firm/settings/{section}` with the version read; a stale second factor
// (403) opens the step-up slot (`ConfirmItsYou`), a stale version (409) asks for a reload. Leaving a
// dirty form asks "Discard changes?" first. Keys a later epic registers (return approval policy,
// AJE thresholds, auto mode, modules, renewal) render only when the section answers them.

type Value = string | number | boolean | null;
type SectionKey = "profile" | "defaults" | "plan";
type Edits = Partial<Record<SectionKey, Record<string, Value>>>;
const SECTIONS: readonly SectionKey[] = ["profile", "defaults", "plan"];

/** A 403 means the save needs a fresh second factor (the matrix gates `firm.manage_settings`). */
function isForbidden(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    error.detail === "forbidden"
  );
}

/** T12's step-up slot (G-01 §5.2): the app's "Confirm it's you" (shell/mfa.tsx), with the copy G-01
 * decides for this save; a fresh sign-in returns here. */
function StepUp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.stepUpTitle}
      description={COPY.stepUpBody}
    >
      <div className="flex justify-end gap-2">
        <Button
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          {COPY.cancel}
        </Button>
        <Button
          onClick={() => {
            signIn(currentRoute(), { forceLogin: true });
          }}
        >
          {COPY.signInAgain}
        </Button>
      </div>
    </Dialog>
  );
}

export interface ADM01Props {
  /** Another section, an At a glance row or an office: its route id ("people", "offices", …). */
  onNavigate?: (section: string) => void;
  onBack?: () => void;
}

function valueOf(
  section: SettingsSectionValuesOut | undefined,
  edits: Edits,
  key: string,
): Value | undefined {
  const id = section?.section;
  const edited = id === undefined ? undefined : edits[id];
  if (edited !== undefined && key in edited) return edited[key] ?? null;
  return section?.values.find((v) => v.key === key)?.value;
}

function has(section: SettingsSectionValuesOut | undefined, key: string): boolean {
  return section?.values.some((v) => v.key === key) ?? false;
}

function editable(section: SettingsSectionValuesOut | undefined, key: string): boolean {
  return section?.values.find((v: SettingValueOut) => v.key === key)?.editable ?? false;
}

function tone(row: GlanceRowOut): "done" | "warn" | "half" | "off" {
  if (row.tone === "ok") return "done";
  if (row.tone === "attention") return "warn";
  return row.tone === "partial" ? "half" : "off";
}

function useSection(key: SectionKey, enabled: boolean) {
  return useQuery({
    ...settingsSectionOptions({ path: { section: key } }),
    enabled,
    retry: false,
  });
}

export function ADM01({ onNavigate, onBack }: ADM01Props): JSX.Element {
  const now = useNow();
  const queryClient = useQueryClient();
  const overview = useQuery({ ...settingsOverviewOptions(), retry: false });
  const visible = (key: SectionKey): boolean =>
    overview.data?.sections.find((s) => s.key === key)?.visible === true;
  const profile = useSection("profile", visible("profile"));
  const defaults = useSection("defaults", visible("defaults"));
  const plan = useSection("plan", visible("plan"));
  const offices = useQuery({ ...officesOptions(), enabled: overview.isSuccess, retry: false });
  const members = useQuery({ ...firmMembersOptions(), enabled: overview.isSuccess, retry: false });
  const save = useMutation(updateSettingsSectionMutation());
  const [edits, setEdits] = useState<Edits>({});
  const [stepUp, setStepUp] = useState(false);
  const [leaving, setLeaving] = useState<(() => void) | null>(null);

  if (overview.isError) {
    // AC1.8: someone without a settings role is answered 404 and sees the not-allowed state.
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <EmptyState title={COPY.notAllowed} />
      </div>
    );
  }

  const sections: Record<SectionKey, SettingsSectionValuesOut | undefined> = {
    profile: profile.data,
    defaults: defaults.data,
    plan: plan.data,
  };
  // Read-only once the section says so (not while it loads, so a firm admin never sees the banner).
  const readOnly =
    profile.data !== undefined && !profile.data.allowed_actions?.includes("firm.manage_settings");
  const dirty = Object.values(edits).some((e) => Object.keys(e).length > 0);
  const displayName = valueOf(profile.data, edits, "display_name");
  const invalid = displayName === null || String(displayName ?? "x").trim() === "";

  function change(section: SectionKey, key: string, value: Value): void {
    setEdits((current) => {
      const base = sections[section]?.values.find((v) => v.key === key)?.value ?? null;
      const rest = Object.fromEntries(
        Object.entries(current[section] ?? {}).filter(([k]) => k !== key),
      );
      return { ...current, [section]: base === value ? rest : { ...rest, [key]: value } };
    });
  }

  function guarded(go: () => void): void {
    if (dirty && !readOnly) setLeaving(() => go);
    else go();
  }

  async function onSave(): Promise<void> {
    for (const key of SECTIONS) {
      const values = edits[key];
      const read = sections[key];
      if (values === undefined || Object.keys(values).length === 0 || read === undefined) continue;
      try {
        await save.mutateAsync({
          path: { section: key },
          body: { version: read.version, values },
        });
      } catch (error) {
        if (isForbidden(error)) setStepUp(true);
        else if (typeof error === "object" && error !== null && "detail" in error) {
          const detail = error.detail;
          toast.show({
            kind: "error",
            text: detail === "stale_version" ? COPY.staleAnonymous : COPY.unavailable,
          });
        }
        return;
      }
    }
    setEdits({});
    await queryClient.invalidateQueries({ queryKey: settingsOverviewQueryKey() });
    for (const key of SECTIONS) {
      await queryClient.invalidateQueries({
        queryKey: settingsSectionQueryKey({ path: { section: key } }),
      });
    }
    toast.show(COPY.saved);
  }

  const rowCommon = (section: SectionKey, key: string) => ({
    label: COPY.rows[key as keyof typeof COPY.rows],
    readOnly: readOnly || !editable(sections[section], key),
  });
  const textRow = (section: SectionKey, key: string, required = false): JSX.Element | null => {
    if (!has(sections[section], key)) return null;
    const value = valueOf(sections[section], edits, key);
    const missing = required && (value === null || String(value ?? "").trim() === "");
    return (
      <ValueRow
        key={key}
        kind="text"
        {...rowCommon(section, key)}
        value={value === null || value === undefined ? "" : String(value)}
        {...(required ? { placeholder: COPY.required } : {})}
        {...(missing ? { error: COPY.displayNameHelp, errorAt: "label" as const } : {})}
        onChange={(text) => {
          change(section, key, required || text !== "" ? text : null);
        }}
      />
    );
  };
  const selectRow = (
    section: SectionKey,
    key: string,
    options: readonly { value: string; label: string }[],
    help?: string,
  ): JSX.Element | null => {
    if (!has(sections[section], key)) return null;
    const value = valueOf(sections[section], edits, key);
    const known = options.some((o) => o.value === value);
    return (
      <ValueRow
        key={key}
        kind="select"
        {...rowCommon(section, key)}
        {...(help === undefined ? {} : { help })}
        value={String(value ?? "")}
        options={known ? options : [...options, { value: String(value), label: String(value) }]}
        onChange={(next) => {
          change(section, key, next);
        }}
      />
    );
  };
  const toggleRow = (section: SectionKey, key: string, help?: string): JSX.Element | null => {
    if (!has(sections[section], key)) return null;
    return (
      <ValueRow
        key={key}
        kind="toggle"
        {...rowCommon(section, key)}
        {...(help === undefined ? {} : { help })}
        checked={valueOf(sections[section], edits, key) === true}
        onChange={(on) => {
          change(section, key, on);
        }}
      />
    );
  };
  const lock = readOnly ? { action: <SettingsLock /> } : {};

  const people = overview.data?.at_a_glance.find((r) => r.key === "people")?.facts ?? {};
  const seatTotal = valueOf(plan.data, edits, "seats");
  const seatless = Number(valueOf(profile.data, edits, "seatless_staff_count") ?? 0);
  const officeRows: readonly FirmOfficeOut[] = offices.data ?? [];
  const returns = officeRows.every((o) => o.facts?.returns !== undefined)
    ? officeRows.reduce((sum, o) => sum + (o.facts?.returns ?? 0), 0)
    : undefined;
  const billing = valueOf(plan.data, edits, "billing_contact_user_id");
  const billingOptions = (members.data ?? []).map((m) => ({
    value: m.user_id,
    label: m.display_name,
  }));
  const modules = valueOf(plan.data, edits, "modules");
  const renewal = valueOf(plan.data, edits, "renewal_on");

  const glance = (
    <section
      aria-label={COPY.glanceTitle}
      className="overflow-hidden rounded-nested bg-card shadow-e1"
    >
      <div className="flex min-h-[33px] items-center justify-between border-b-[0.5px] border-hair bg-band-hd px-[12px]">
        <h3 className="text-section">{COPY.glanceTitle}</h3>
        <span className="text-meta text-ink-3">{COPY.updated(time(now))}</span>
      </div>
      <ul className="flex flex-col">
        {(overview.data?.at_a_glance ?? []).map((row) => {
          const words = GLANCE[row.key];
          if (words === undefined) return null;
          return (
            <li key={row.key} className="border-b-[0.5px] border-hair last:border-b-0">
              <button
                type="button"
                className="flex min-h-[44px] w-full items-center gap-[10px] px-[12px] py-[6px] text-left hover:bg-nav-fill"
                onClick={() => {
                  guarded(() => onNavigate?.(words.section));
                }}
              >
                {row.unavailable === true ? (
                  <span className="w-[15px] flex-none" />
                ) : (
                  <StatusDisc state={tone(row)} />
                )}
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-body font-medium">{words.name}</span>
                  <span className="text-meta text-ink-3">
                    {row.unavailable === true ? COPY.unavailable : words.line(row.facts ?? {})}
                  </span>
                </span>
                <Icon name="chevron-right" size={12} className="flex-none text-ink-3" />
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );

  return (
    <SettingsLayout
      bare
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.title}
      context={overview.data?.firm_name ?? ""}
      backLabel={COPY.back}
      onBack={() => {
        guarded(() => onBack?.());
      }}
      navTitle={COPY.navTitle}
      groups={GROUPS.map((g) => ({
        ...g,
        sections: g.sections.filter(
          (s) => s.id === "general" || s.id === "people" || s.id === "offices" || PLANNED_VISIBLE,
        ),
      })).filter((g) => g.sections.length > 0)}
      active="general"
      onSelect={(id) => {
        if (id !== "general") guarded(() => onNavigate?.(id));
      }}
      dirty={dirty}
      invalid={invalid}
      readOnly={readOnly}
      readOnlyText={COPY.readOnly}
      labels={{ unsaved: COPY.unsaved }}
      onDiscard={() => {
        setEdits({});
      }}
      onSave={() => {
        void onSave();
      }}
      aside={glance}
      stepUp={<StepUp open={stepUp} onOpenChange={setStepUp} />}
      overlay={
        <ConfirmDialog
          open={leaving !== null}
          onOpenChange={(open) => {
            if (!open) setLeaving(null);
          }}
          title={COPY.discardTitle}
          confirmLabel={COPY.discardConfirm}
          cancelLabel={COPY.keepEditing}
          onConfirm={() => {
            const go = leaving;
            setEdits({});
            setLeaving(null);
            go?.();
          }}
        >
          {COPY.discardBody}
        </ConfirmDialog>
      }
    >
      {profile.data !== undefined && (
        <Fieldset title={COPY.fieldsets.profile} flush className="mb-0" {...lock}>
          {textRow("profile", "legal_name")}
          {textRow("profile", "display_name", true)}
          <ValueRow
            kind="value"
            label={COPY.rows.region}
            readOnly={readOnly}
            help={COPY.regionHelp}
            trailing="lock"
          >
            {COPY.regionValue}
          </ValueRow>
          {selectRow("profile", "time_zone", COPY.timeZones)}
          {textRow("profile", "intake_mailbox")}
          {textRow("profile", "website")}
          <ValueRow kind="value" label={COPY.rows.logo} readOnly={readOnly}>
            <FirmMark name={overview.data?.firm_name ?? ""} mark="wave" size={20} />
            {!readOnly && PLANNED_VISIBLE && <span>{COPY.replaceLogo}</span>}
          </ValueRow>
        </Fieldset>
      )}
      {officeRows.length > 0 && (
        <Fieldset
          title={COPY.fieldsets.offices}
          flush
          className="mb-0"
          {...(readOnly
            ? lock
            : PLANNED_VISIBLE
              ? { action: <FieldsetAdd>{COPY.addOffice}</FieldsetAdd> }
              : {})}
        >
          {officeRows.map((o) => (
            <ValueRow
              key={o.id}
              kind="value"
              label={COPY.officeName(o.name, o.is_hq)}
              readOnly={readOnly}
              trailing="chevron-right"
            >
              {COPY.office(o.seats, o.facts?.returns, o.is_hq)}
            </ValueRow>
          ))}
          <div
            data-settings="total"
            className="flex h-[30px] items-center justify-between bg-sel-bg px-[12px] text-body font-medium"
          >
            <span>{COPY.allOffices}</span>
            <span>
              {COPY.allOfficesValue(
                officeRows.reduce((sum, o) => sum + o.seats, 0),
                returns,
              )}
            </span>
          </div>
        </Fieldset>
      )}
      {plan.data !== undefined && (
        <Fieldset title={COPY.fieldsets.plan} flush className="mb-0" {...lock}>
          {typeof seatTotal === "number" && (
            <ValueRow
              kind="value"
              label={COPY.rows.seats}
              readOnly={readOnly}
              {...((people.used ?? 0) >= seatTotal
                ? { help: COPY.seatsFull, helpTone: "amber" as const }
                : {})}
            >
              {COPY.seatsUsed(people.used ?? 0, seatTotal)}
            </ValueRow>
          )}
          {typeof seatTotal === "number" && (
            <ValueRow
              kind="value"
              label={COPY.rows.people}
              readOnly={readOnly}
              help={COPY.peopleLine(
                people.partners ?? 0,
                (people.used ?? 0) -
                  (people.pending ?? 0) -
                  (people.partners ?? 0) -
                  (people.operations ?? 0),
                (people.operations ?? 0) + seatless,
                seatless,
              )}
            >
              {String((people.used ?? 0) - (people.pending ?? 0) + seatless)}
            </ValueRow>
          )}
          {typeof modules === "string" && (
            <ValueRow kind="value" label={COPY.rows.modules} readOnly={readOnly}>
              {modules
                .split(",")
                .map((m) => COPY.modules[m] ?? m)
                .join(" · ")}
            </ValueRow>
          )}
          {typeof renewal === "string" && (
            <ValueRow kind="value" label={COPY.rows.renewal_on} readOnly={readOnly}>
              {date(renewal, { now, withYear: true })}
            </ValueRow>
          )}
          {has(plan.data, "billing_contact_user_id") && (
            <ValueRow
              kind="select"
              {...rowCommon("plan", "billing_contact_user_id")}
              value={String(billing ?? "")}
              options={billingOptions}
              onChange={(next) => {
                change("plan", "billing_contact_user_id", next);
              }}
            />
          )}
        </Fieldset>
      )}
      {defaults.data !== undefined && (
        <Fieldset title={COPY.fieldsets.defaults} flush className="mb-0" {...lock}>
          {selectRow("defaults", "return_approval_policy", [], COPY.help.return_approval_policy)}
          {selectRow("defaults", "aje_threshold_policy", [], COPY.help.aje_threshold_policy)}
          {toggleRow("defaults", "auto_mode_new_audits", COPY.help.auto_mode_new_audits)}
          {toggleRow("defaults", "portal_secured_footer")}
          {selectRow("defaults", "week_starts_on", COPY.weekStarts)}
        </Fieldset>
      )}
    </SettingsLayout>
  );
}
