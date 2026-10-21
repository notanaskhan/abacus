import type { SignOffLevelOut, WorkingPaperOut } from "@abacus/api-client";
import {
  createWorkpaperMutation,
  workpapersOptions,
  workpapersQueryKey,
} from "@abacus/api-client/query";
import {
  Alert,
  Button,
  type Column,
  DataTable,
  EmptyState,
  Fieldset,
  registryWord,
  Sheet,
  Skeleton,
  StatusPill,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-308 (TASK-319): the engagement's working papers. Status uses the registry's audit_section
// words; the squares are the five sign-off levels (L1 preparer to L5 EQR), struck when stale.

export const LEVEL_SHORT: Record<SignOffLevelOut["name"], string> = {
  preparer: "P",
  reviewer: "R",
  manager: "M",
  partner: "EP",
  eqr: "EQR",
};

export function initials(name: string | null | undefined): string {
  return (name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 3);
}

export function statusWord(w: WorkingPaperOut): ReturnType<typeof registryWord> {
  const preparer = w.levels.find((l) => l.level === 1)?.signed_by_name;
  const reviewer = [...w.levels]
    .reverse()
    .find((l) => (l.level === 2 || l.level === 3) && l.signed_by_name)?.signed_by_name;
  const who = w.status === "prepared" ? preparer : w.status === "reviewed" ? reviewer : null;
  return registryWord("audit_section", w.status, { fill: { initials: initials(who) } });
}

export function SignOffSquares({ levels }: { levels: SignOffLevelOut[] }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1" aria-label="Sign-offs">
      {levels.map((l) => {
        const signed = l.signed_by_name != null;
        const label = signed
          ? `${LEVEL_SHORT[l.name]} signed by ${l.signed_by_name ?? ""}${l.stale ? ", changed since" : ""}`
          : `${LEVEL_SHORT[l.name]} not signed`;
        return (
          <span
            key={l.level}
            title={label}
            aria-label={label}
            className={
              "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[3px] px-1 text-[10.5px] font-medium tabular-nums " +
              (signed
                ? l.stale
                  ? "bg-amber-tint text-ink-2 line-through"
                  : "bg-green-tint text-ink"
                : "bg-nested text-ink-4 inset-shadow-hair")
            }
          >
            {signed ? initials(l.signed_by_name) : LEVEL_SHORT[l.name]}
          </span>
        );
      })}
    </span>
  );
}

export function Workpapers({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const list = useQuery({ ...workpapersOptions(path), retry: false });
  const [creating, setCreating] = useState(false);
  if (list.isPending) return <Skeleton className="h-64" />;
  if (list.isError) {
    return (
      <Alert title="Working papers aren't available">
        {errorMessage(list.error) === "forbidden"
          ? "Working papers are for the engagement team."
          : errorMessage(list.error)}
      </Alert>
    );
  }
  const columns: Column<WorkingPaperOut>[] = [
    {
      key: "code",
      header: "Ref",
      cell: (w) => (
        <Link
          to="/engagements/$engagementId/workpapers/$workpaperId"
          params={{ engagementId, workpaperId: w.id }}
          className="font-medium tabular-nums text-ink hover:underline"
        >
          {w.code}
        </Link>
      ),
    },
    { key: "title", header: "Title", cell: (w) => w.title },
    { key: "area", header: "Audit area", cell: (w) => w.audit_area ?? "—" },
    {
      key: "status",
      header: "Status",
      cell: (w) => {
        const word = statusWord(w);
        return <StatusPill tone={word.tone}>{word.label}</StatusPill>;
      },
    },
    { key: "signoffs", header: "Sign-offs", cell: (w) => <SignOffSquares levels={w.levels} /> },
    {
      key: "cells",
      header: "Cells · sources",
      cell: (w) => (
        <span className="tabular-nums text-ink-3">{`${String(w.cells)} · ${String(w.citations)}`}</span>
      ),
    },
  ];
  return (
    <section
      aria-labelledby="wp-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id="wp-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Working papers
        </h2>
        <span className="text-[12.5px] text-ink-3 tabular-nums">{list.data.length}</span>
        <span className="flex-1" />
        <Button
          size="sm"
          onClick={() => {
            setCreating(true);
          }}
        >
          New working paper
        </Button>
      </div>
      {list.data.length === 0 ? (
        <EmptyState title="No working papers yet">
          Create a lead schedule or testing paper; cells, formulas, sources and sign-offs live on
          it.
        </EmptyState>
      ) : (
        <DataTable
          rows={list.data}
          columns={columns}
          rowKey={(w) => w.id}
          label="Working papers"
        />
      )}
      {creating && (
        <NewWorkpaper
          engagementId={engagementId}
          onClose={() => {
            setCreating(false);
          }}
        />
      )}
    </section>
  );
}

const CODE = /^[A-Z0-9][A-Z0-9.-]{0,19}$/;

function NewWorkpaper({
  engagementId,
  onClose,
}: {
  engagementId: string;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [area, setArea] = useState("");
  const create = useMutation({
    ...createWorkpaperMutation(),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({
        queryKey: workpapersQueryKey({ path: { engagement_id: engagementId } }),
      });
      onClose();
      void navigate({
        to: "/engagements/$engagementId/workpapers/$workpaperId",
        params: { engagementId, workpaperId: created.workpaper.id },
      });
    },
    onError: (e) => {
      const code = errorMessage(e);
      toast.show(
        code === "workpaper_code_taken"
          ? "That reference is already used on this engagement."
          : code === "no_assurance_item"
            ? "Only an audit or attest engagement holds working papers."
            : code,
      );
    },
  });
  const clean = code.trim().toUpperCase();
  const ok = CODE.test(clean) && title.trim() !== "";
  const input = "h-[30px] w-[240px] rounded-tile border-0 bg-nested px-2.5 inset-shadow-hair";
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title="New working paper"
      footer={
        <Button
          disabled={!ok || create.isPending}
          onClick={() => {
            create.mutate({
              path: { engagement_id: engagementId },
              body: {
                code: clean,
                title: title.trim(),
                ...(area.trim() === "" ? {} : { audit_area: area.trim() }),
              },
            });
          }}
        >
          Create
        </Button>
      }
    >
      <Fieldset>
        <div className="flex flex-col gap-2 text-[13px]">
          <label className="flex items-center justify-between gap-3">
            Reference
            <input
              value={code}
              maxLength={20}
              placeholder="C-100"
              onChange={(e) => {
                setCode(e.target.value);
              }}
              className={input}
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            Title
            <input
              value={title}
              maxLength={200}
              placeholder="Cash lead schedule"
              onChange={(e) => {
                setTitle(e.target.value);
              }}
              className={input}
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            Audit area
            <input
              value={area}
              maxLength={120}
              placeholder="Cash"
              onChange={(e) => {
                setArea(e.target.value);
              }}
              className={input}
            />
          </label>
        </div>
      </Fieldset>
    </Sheet>
  );
}
