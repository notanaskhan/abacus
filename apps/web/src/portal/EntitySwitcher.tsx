import type { MePortalScopeOut } from "@abacus/api-client";
import { Icon, Menu } from "@abacus/ui";
import type { JSX } from "react";

// The portal's EntitySwitcher (P-08-T07; DEC-129): one person may hold grants on several clients
// or entities (Meera Shah: her own return and a Ridgeline K-1). The switcher lists the scopes of
// `/v1/me` → `portal.scopes` by their labels and role; choosing one re-reads the home for it. A
// person with one scope sees its label only. Scope labels are the client's own names (portal data,
// never the firm's internal codes).

export interface EntitySwitcherProps {
  scopes: readonly MePortalScopeOut[];
  value: string | undefined;
  onChange: (scopeId: string) => void;
}

export function EntitySwitcher({
  scopes,
  value,
  onChange,
}: EntitySwitcherProps): JSX.Element | null {
  const current = scopes.find((s) => s.id === value) ?? scopes[0];
  if (current === undefined) return null;
  const label = (
    <span className="flex min-w-0 flex-col items-start">
      <span className="truncate text-body font-medium">{current.label}</span>
      <span className="text-meta text-ink-3">{current.role_label}</span>
    </span>
  );
  if (scopes.length < 2) {
    return (
      <div data-portal="entity" className="px-[12px] py-[10px]">
        {label}
      </div>
    );
  }
  return (
    <Menu
      label={current.label}
      sections={[
        scopes.map((s) => ({
          label: s.label,
          hint: s.role_label,
          checked: s.id === current.id,
          onSelect: () => {
            onChange(s.id);
          },
        })),
      ]}
      trigger={
        <button
          type="button"
          data-portal="entity"
          aria-label={current.label}
          className="flex w-full items-center justify-between gap-[8px] rounded-nested px-[12px] py-[10px] text-left hover:bg-nav-fill"
        >
          {label}
          <Icon name="chevrons-up-down" size={12} className="flex-none text-ink-3" />
        </button>
      }
    />
  );
}
