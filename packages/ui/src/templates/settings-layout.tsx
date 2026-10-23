import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { Icon, type IconName } from "../icons";
import { AppShell } from "../layout/app-shell";
import { Pane } from "../layout/pane";
import { RecordHeader } from "../layout/record-header";
import type { ToolbarProps } from "../layout/toolbar";

// T12 SettingsLayout (F-05-T45; Wave 0 - Foundations `#t12`, Wave 0 - Templates TPL-12): the
// toolbar with the firm pill pressed; the 42 settings bar (Back, "Firm settings" and the firm's
// name centred); in read-only, the 32 amber banner under it; then the 240 section list beside the
// form pane, whose well stacks 760 fieldset cards of value rows. No boxed inputs, no native selects.
//
// The form state is the screen's: the layout draws Save enabled only when the form is dirty and
// valid, Discard only when dirty, "Unsaved changes" beside them, and in read-only none of the three.
// A save the server refuses for want of a fresh second factor opens the step-up slot, which the app
// fills with its own `ConfirmItsYou` (apps/web/src/shell/mfa.tsx); this package imports nothing
// from the app.

export interface SettingsSection {
  id: string;
  label: string;
  icon: IconName;
}

export interface SettingsGroup {
  /** Drawn in the tracked caps role ("FIRM"); written as the handoff writes it. */
  label: string;
  sections: readonly SettingsSection[];
}

export interface SettingsLayoutProps {
  toolbar: ToolbarProps;
  /** Presentation only (the gallery): a framed 1400 window. */
  embedded?: boolean;
  height?: number;
  /** "Firm settings" */
  title: string;
  /** "Brightwater Hale LLP" */
  context?: string;
  backLabel?: string;
  onBack?: () => void;
  /** The section list's pane title: "Settings". */
  navTitle: string;
  groups: readonly SettingsGroup[];
  active: string;
  onSelect?: (id: string) => void;
  /** Something differs from what is saved. */
  dirty: boolean;
  /** A field fails its check ("Required"): Save is blocked. */
  invalid?: boolean;
  /** The viewer cannot edit: the banner shows and Save, Discard and "Unsaved changes" do not. */
  readOnly?: boolean;
  /** "Only firm admins can edit these settings." */
  readOnlyText?: string;
  /** Where the read-only banner sits: under the settings bar across the window, in place of the
   * form's actions (TPL-12d), or at the top of the form over a disabled Save (T12c). */
  readOnlyAt?: "bar" | "form";
  onSave?: () => void;
  onDiscard?: () => void;
  labels?: { save?: string; discard?: string; unsaved?: string };
  /** Drawn over the shell when a save needs a fresh second factor: the app's step-up dialog. */
  stepUp?: ReactNode;
  /** Drawn over the shell: the toast host, a discard guard. */
  overlay?: ReactNode;
  /** The active section's form: fieldsets of value rows. */
  children: ReactNode;
}

/** Can the form be saved: dirty, valid and editable. */
export function canSave(dirty: boolean, invalid: boolean, readOnly: boolean): boolean {
  return dirty && !invalid && !readOnly;
}

function SectionList({
  groups,
  active,
  onSelect,
}: Pick<SettingsLayoutProps, "groups" | "active" | "onSelect">): JSX.Element {
  return (
    <nav aria-label="Sections" className="flex flex-col px-[6px] pb-[10px]">
      {groups.map((group) => (
        <div key={group.label} className="flex flex-col">
          <h3 className="px-[8px] pt-[14px] pb-[6px] text-outline-hd text-ink-3 uppercase">
            {group.label}
          </h3>
          <ul className="flex flex-col gap-[1px]">
            {group.sections.map((s) => {
              const on = s.id === active;
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    aria-current={on ? "page" : undefined}
                    onClick={() => {
                      onSelect?.(s.id);
                    }}
                    className={cn(
                      "flex h-[33px] w-full items-center gap-[9px] rounded-tile px-[8px] text-left text-body",
                      on ? "bg-sel-bg font-medium" : "hover:bg-nav-fill",
                    )}
                  >
                    <Icon name={s.icon} size={14} className="shrink-0 text-ink-3" />
                    <span className="min-w-0 truncate">{s.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/** The fieldset header's lock in read-only (TPL-12d): a 12px lock in ink-3, named for readers. */
export function SettingsLock({ label = "Locked" }: { label?: string }): JSX.Element {
  return <Icon name="lock" size={12} label={label} className="mr-[4px] text-ink-3" />;
}

export function SettingsLayout({
  toolbar,
  embedded = false,
  height,
  title,
  context,
  backLabel = "Back",
  onBack,
  navTitle,
  groups,
  active,
  onSelect,
  dirty,
  invalid = false,
  readOnly = false,
  readOnlyText,
  readOnlyAt = "bar",
  onSave,
  onDiscard,
  labels,
  stepUp,
  overlay,
  children,
}: SettingsLayoutProps): JSX.Element {
  const formTitle =
    groups.flatMap((g) => g.sections).find((s) => s.id === active)?.label ?? navTitle;
  const showDirty = dirty && !readOnly;
  const banner =
    readOnlyText === undefined ? null : (
      <div
        role="status"
        data-settings="read-only"
        className={cn(
          "flex h-[32px] flex-none items-center gap-[7px] rounded-tile bg-amber-tint px-[12px] text-dense text-amber-ink",
          readOnlyAt === "bar" && "mx-(--edge-app)",
        )}
      >
        <Icon name="lock" size={13} />
        {readOnlyText}
      </div>
    );
  const record = (
    <>
      <RecordHeader
        variant="settings"
        title={title}
        {...(context === undefined ? {} : { context })}
        backLabel={backLabel}
        {...(onBack === undefined ? {} : { onBack })}
      />
      {readOnly && readOnlyAt === "bar" && banner}
    </>
  );
  const readOnlyActions =
    readOnlyAt === "form" ? (
      <Button size="lg" disabled>
        {labels?.save ?? "Save"}
      </Button>
    ) : undefined;
  const actions = readOnly ? (
    readOnlyActions
  ) : (
    <>
      {showDirty && (
        <span data-settings="unsaved" className="pr-[8px] text-body text-ink-3">
          {labels?.unsaved ?? "Unsaved changes"}
        </span>
      )}
      <Button variant="ghost" size="lg" disabled={!showDirty} onClick={onDiscard}>
        {labels?.discard ?? "Discard"}
      </Button>
      <Button size="lg" disabled={!canSave(dirty, invalid, readOnly)} onClick={onSave}>
        {labels?.save ?? "Save"}
      </Button>
    </>
  );
  return (
    <AppShell
      {...(embedded ? { embedded: true } : {})}
      {...(height === undefined ? {} : { height })}
      toolbar={{ active: "", firmPressed: true, ...toolbar }}
      record={record}
      overlay={
        <>
          {overlay}
          {stepUp}
        </>
      }
    >
      <Pane width={240} title={navTitle}>
        <SectionList groups={groups} active={active} {...(onSelect ? { onSelect } : {})} />
      </Pane>
      <Pane
        title={formTitle}
        titleAlign="left"
        scrollLabel={formTitle}
        {...(actions === undefined ? {} : { right: actions })}
      >
        <div
          data-settings="form"
          {...(readOnly ? { "data-read-only": "" } : {})}
          className="px-[12px] pt-[12px] pb-[24px]"
        >
          <div className="flex max-w-[760px] flex-col gap-[12px]">
            {readOnly && readOnlyAt === "form" && banner}
            {children}
          </div>
        </div>
      </Pane>
    </AppShell>
  );
}
