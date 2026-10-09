import type { EngagementIn, RollForwardProposalOut, ProposedItemOut } from "@abacus/api-client";
import { createEngagementMutation } from "@abacus/api-client/query";
import { Alert, Badge, Button } from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

type StaffRole = "engagement_partner" | "manager" | "senior" | "staff" | "reviewer";
const ROLES: [StaffRole, string][] = [
  ["engagement_partner", "Engagement partner"],
  ["manager", "Manager"],
  ["senior", "Senior"],
  ["staff", "Staff"],
  ["reviewer", "Reviewer"],
];
const SELECT = "h-8 rounded-[var(--radius-control)] border border-line bg-surface px-2 text-sm";
const GROUPS: [ProposedItemOut["kind"], string][] = [
  ["used", "Used last year"],
  ["not_used", "Not used last year"],
  ["new_in_template", "New in the template"],
];

function itemKey(item: ProposedItemOut): string {
  return item.prior_item_id ?? `template:${String(item.template_key)}`;
}

/** SPEC-025 AC-2 (TASK-048): review last year's team, template and items, then create exactly
 * what's ticked. Nothing exists until "Create engagement". */
export function RollForwardReview({
  proposal,
  body,
  onBack,
  onChoosePrior,
  onCreated,
}: {
  proposal: RollForwardProposalOut;
  body: EngagementIn;
  onBack: () => void;
  onChoosePrior: (engagementId: string) => void;
  onCreated: (engagementId: string) => void;
}): JSX.Element {
  const prior = proposal.prior;
  const [team, setTeam] = useState<Record<string, { on: boolean; role: StaffRole }>>(() =>
    Object.fromEntries(proposal.team.map((m) => [m.user_id, { on: m.available, role: m.role }])),
  );
  const [ticked, setTicked] = useState<Set<string>>(
    () => new Set(proposal.items.filter((i) => i.ticked).map(itemKey)),
  );
  const create = useMutation({
    ...createEngagementMutation(),
    onSuccess: (engagement) => {
      onCreated(engagement.id);
    },
  });
  if (prior === null) return <></>;
  const counts = Object.fromEntries(
    GROUPS.map(([kind]) => [kind, proposal.items.filter((i) => i.kind === kind).length]),
  ) as Record<ProposedItemOut["kind"], number>;
  const confirm = (): void => {
    const chosen = proposal.items.filter((i) => ticked.has(itemKey(i)));
    create.mutate({
      body: {
        ...body,
        roll_forward: {
          prior_engagement_id: prior.engagement_id,
          team: proposal.team
            .filter((m) => m.available && team[m.user_id]?.on === true)
            .map((m) => ({ user_id: m.user_id, role: team[m.user_id]?.role ?? m.role })),
          version_id: proposal.template?.latest_version_id ?? null,
          prior_item_ids: chosen.flatMap((i) =>
            i.prior_item_id == null ? [] : [i.prior_item_id],
          ),
          template_keys: chosen.flatMap((i) => (i.template_key == null ? [] : [i.template_key])),
        },
      },
    });
  };
  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="flex flex-col gap-1">
        <p>
          Rolling forward from <span className="font-semibold">{prior.name}</span> (
          {prior.fiscal_period_start} – {prior.fiscal_period_end}).
        </p>
        {proposal.others.length > 0 && (
          <label className="flex items-center gap-2 text-muted">
            Another earlier engagement:
            <select
              className={SELECT}
              value={prior.engagement_id}
              onChange={(e) => {
                onChoosePrior(e.target.value);
              }}
            >
              <option value={prior.engagement_id}>{prior.name}</option>
              {proposal.others.map((o) => (
                <option key={o.engagement_id} value={o.engagement_id}>
                  {o.name} ({o.fiscal_period_end})
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <section aria-label="Team" className="flex flex-col gap-2">
        <h3 className="font-semibold">Team</h3>
        <p className="text-xs text-muted">You join as engagement partner.</p>
        {proposal.team.length === 0 && <p className="text-muted">No one else from last year.</p>}
        <ul className="flex flex-col gap-1">
          {proposal.team.map((m) => {
            const row = team[m.user_id];
            return (
              <li key={m.user_id} className="flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    disabled={!m.available}
                    checked={m.available && row?.on === true}
                    onChange={(e) => {
                      setTeam({
                        ...team,
                        [m.user_id]: { on: e.target.checked, role: row?.role ?? m.role },
                      });
                    }}
                  />
                  {m.display_name}
                </label>
                {m.available ? (
                  <select
                    aria-label={`Role for ${m.display_name}`}
                    className={SELECT}
                    value={row?.role ?? m.role}
                    onChange={(e) => {
                      setTeam({
                        ...team,
                        [m.user_id]: { on: row?.on ?? true, role: e.target.value as StaffRole },
                      });
                    }}
                  >
                    {ROLES.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="text-xs text-muted">
                    Not available: left the firm or now walled from this client
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-label="Template" className="flex flex-col gap-1">
        <h3 className="font-semibold">Template</h3>
        {proposal.template === null ? (
          <p className="text-muted">Last year&apos;s engagement had no template.</p>
        ) : (
          <p>
            {proposal.template.template_name} · v{proposal.template.latest_version}
            {proposal.template.latest_version !== proposal.template.version_last_year &&
              ` (v${String(proposal.template.version_last_year)} last year)`}
          </p>
        )}
      </section>

      <section aria-label="Request list" className="flex flex-col gap-2">
        <h3 className="font-semibold">Request list</h3>
        <p className="text-muted">
          {counts.used} of {counts.used + counts.not_used} used last year, {counts.not_used} not
          used, {counts.new_in_template} new in the template.
        </p>
        {GROUPS.map(([kind, label]) =>
          counts[kind] === 0 ? null : (
            <details key={kind} open={kind !== "not_used"} className="flex flex-col gap-1">
              <summary className="cursor-pointer font-medium">
                {label} ({counts[kind]})
              </summary>
              <ul className="flex max-h-56 flex-col gap-1 overflow-y-auto pl-2">
                {proposal.items
                  .filter((i) => i.kind === kind)
                  .map((i) => {
                    const key = itemKey(i);
                    return (
                      <li key={key}>
                        <label className="flex items-start gap-2">
                          <input
                            type="checkbox"
                            checked={ticked.has(key)}
                            onChange={(e) => {
                              const next = new Set(ticked);
                              if (e.target.checked) next.add(key);
                              else next.delete(key);
                              setTicked(next);
                            }}
                          />
                          <span>
                            {i.description}{" "}
                            <span className="text-xs text-muted">{i.audit_area}</span>
                            {kind === "new_in_template" && <Badge className="ml-2">New</Badge>}
                          </span>
                        </label>
                      </li>
                    );
                  })}
              </ul>
            </details>
          ),
        )}
      </section>

      {create.isError && (
        <Alert title="Couldn't create the engagement">{errorMessage(create.error)}</Alert>
      )}
      <div className="flex justify-between gap-2">
        <Button type="button" variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button type="button" disabled={create.isPending} onClick={confirm}>
          {create.isPending ? "Creating…" : "Create engagement"}
        </Button>
      </div>
    </div>
  );
}
