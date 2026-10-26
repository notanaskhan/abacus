// SHL-08d password-locked (P-03-T20; P-03 F5, AC5.1, AC5.3, AC5.4; C4 §3.5): the Lock tile, "This
// PDF is password-protected.", the Password field with Unlock, and "Ask Jonah & Claire Feld…".
//
// - The password is sent once through the generated SDK function (never React Query, so no cache
//   holds the request), the field is `type=password` with `autocomplete=off`, and it is cleared the
//   moment the form is submitted. Nothing here logs, stores or echoes it.
// - A wrong password answers 200 `wrong_password`: "That password didn't open the file." tied to the
//   field by `aria-describedby`. 429 `unlock_rate_limited` gives the wait.
// - On `ready` the manifest is asked again: it now reads the derivation's masked pages.
// - Flag off, or a person without `evidence.unlock`: the state with "Ask …" only (P-03 §4.9).
// - "Ask …" opens SHL-14 prefilled through the host's `onAskClient`; a host without one draws the
//   link with its destination as a hint (the handoff's tooltip-only link, as "Open in Files").

import { unlockVersion } from "@abacus/api-client";
import { viewerManifestQueryKey } from "@abacus/api-client/query";
import { Button, Icon } from "@abacus/ui";
import { useQueryClient } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useId, useState } from "react";
import { COPY } from "./copy";

export interface LockedTarget {
  /** Who sent the client the password ("Halvard"). */
  issuer?: string | null;
  /** The client the "Ask …" link names ("Jonah & Claire Feld"). */
  client?: string | null;
  /** Opens SHL-14 with a prefilled request for this file's password. */
  onAskClient?: ((prefill: { versionId: string; fileName: string }) => void) | null;
}

function retryMinutes(error: unknown): number | null {
  if (typeof error !== "object" || error === null) return null;
  const body = error as { detail?: unknown; facts?: { retry_after?: unknown } };
  if (body.detail !== "unlock_rate_limited") return null;
  const seconds = Number(body.facts?.retry_after ?? 0);
  return Math.max(1, Math.ceil(seconds / 60));
}

export function UnlockPanel({
  versionId,
  fileName,
  canUnlock,
  locked,
}: {
  versionId: string;
  fileName: string;
  canUnlock: boolean;
  locked: LockedTarget | null;
}): JSX.Element {
  const queryClient = useQueryClient();
  const fieldId = useId();
  const errorId = useId();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = (e: SyntheticEvent): void => {
    e.preventDefault();
    const sent = password;
    setPassword(""); // AC5.4: cleared on submit, before anything answers
    setError(null);
    setBusy(true);
    void unlockVersion({
      path: { version_id: versionId },
      body: { password: sent },
      throwOnError: true,
    })
      .then(({ data }) => {
        if (data.status === "wrong_password") {
          setError(COPY.locked.wrong);
          return;
        }
        void queryClient.invalidateQueries({
          queryKey: viewerManifestQueryKey({ path: { version_id: versionId } }),
        });
      })
      .catch((failure: unknown) => {
        const minutes = retryMinutes(failure);
        setError(minutes === null ? COPY.locked.failed : COPY.locked.limited(minutes));
      })
      .finally(() => {
        setBusy(false);
      });
  };

  const issuer = locked?.issuer ?? null;
  const client = locked?.client ?? null;
  const ask = locked?.onAskClient ?? null;
  return (
    <div
      data-unlock=""
      className="flex flex-1 flex-col items-center justify-center gap-[10px] p-[24px] text-center"
    >
      <span className="inline-flex size-[34px] items-center justify-center rounded-tile bg-nested text-ink-3">
        <Icon name="lock" size={17} />
      </span>
      <p className="text-body font-medium">{COPY.locked.title}</p>
      <p className="max-w-[340px] text-para text-ink-2">
        {issuer === null ? COPY.locked.bodyPlain : COPY.locked.body(issuer)}
      </p>
      {canUnlock && (
        <form onSubmit={submit} className="flex items-center gap-[8px]">
          <label htmlFor={fieldId} className="sr-only">
            {COPY.locked.password}
          </label>
          <input
            id={fieldId}
            type="password"
            autoComplete="off"
            placeholder={COPY.locked.password}
            value={password}
            maxLength={256}
            {...(error === null ? {} : { "aria-describedby": errorId, "aria-invalid": true })}
            onChange={(e) => {
              setPassword(e.target.value);
            }}
            className="h-[36px] w-[200px] rounded-tile border-0 bg-nested px-[12px] text-body outline-none placeholder:text-ink-3"
          />
          <Button type="submit" size="xl" disabled={password === "" || busy}>
            {COPY.locked.unlock}
          </Button>
        </form>
      )}
      {error !== null && (
        <p id={errorId} role="alert" className="text-meta text-danger">
          {error}
        </p>
      )}
      {client !== null && (
        <Button
          variant="link"
          {...(ask === null
            ? { disabled: true, title: COPY.locked.askHint }
            : {
                onClick: () => {
                  ask({ versionId, fileName });
                },
              })}
        >
          {COPY.locked.ask(client)}
        </Button>
      )}
    </div>
  );
}
