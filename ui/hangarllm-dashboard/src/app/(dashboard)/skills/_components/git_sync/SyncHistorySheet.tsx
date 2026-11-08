"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { StatusBadge } from "@/components/shared/table_cells";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { decideGitSkillSync, listGitSkillSyncs } from "@/components/networking";
import type { GitSource, GitSync, SyncDecision } from "@/components/claude_code_plugins/gitSyncTypes";
import { toast } from "@/lib/toast";

import { SYNC_STATUS_TONE, canRollBackTo, commitUrl, shortSha } from "./attention";
import SyncReportView, { SyncSummaryText } from "./SyncReportView";

interface SyncRowProps {
  sync: GitSync;
  source: GitSource;
  busy: boolean;
  onDecide: (sync: GitSync, decision: SyncDecision) => void;
}

function SyncRow({ sync, source, busy, onDecide }: SyncRowProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(sync.status === "pending_approval" || sync.status === "failed");
  const isCurrent = sync.commit_sha !== null && sync.commit_sha === source.applied_sha && sync.report.applied;
  return (
    <li className="rounded-lg border p-3" data-testid={`sync-row-${sync.sync_id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-expanded={expanded}
          aria-label={expanded ? t("skills.gitSync.history.hide") : t("skills.gitSync.history.details")}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </Button>
        <StatusBadge tone={SYNC_STATUS_TONE[sync.status]} label={t(`skills.gitSync.syncStatus.${sync.status}`)} />
        {isCurrent && <StatusBadge tone="info" label={t("skills.gitSync.history.current")} />}
        <span className="text-xs text-muted-foreground">{t(`skills.gitSync.trigger.${sync.trigger}`)}</span>
        {sync.commit_sha && (
          <a
            className="font-mono text-xs text-primary hover:underline"
            href={sync.commit_url ?? commitUrl(source.repository_url, sync.commit_sha)}
            target="_blank"
            rel="noreferrer"
          >
            {shortSha(sync.commit_sha)}
          </a>
        )}
        <span className="text-xs text-muted-foreground" title={sync.started_at}>
          {formatDistanceToNow(new Date(sync.started_at), { addSuffix: true })}
        </span>
        <SyncSummaryText summary={sync.report.summary} />
        <div className="ml-auto flex gap-2">
          {sync.status === "pending_approval" && (
            <>
              <Button size="sm" disabled={busy} onClick={() => onDecide(sync, "approve")}>
                {t("skills.gitSync.history.approve")}
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => onDecide(sync, "reject")}>
                {t("skills.gitSync.history.reject")}
              </Button>
            </>
          )}
          {canRollBackTo(sync.status, sync.commit_sha, source.applied_sha) && (
            <Button size="sm" variant="outline" disabled={busy} onClick={() => onDecide(sync, "rollback")}>
              {t("skills.gitSync.history.rollback")}
            </Button>
          )}
        </div>
      </div>
      {expanded && (
        <div className="mt-3 border-t pt-3">
          <SyncReportView report={sync.report} />
        </div>
      )}
    </li>
  );
}

interface SyncHistorySheetProps {
  accessToken: string;
  source: GitSource;
  onClose: () => void;
  onChanged: () => void;
}

export default function SyncHistorySheet({ accessToken, source, onClose, onChanged }: SyncHistorySheetProps) {
  const { t } = useTranslation();
  const [rollbackTarget, setRollbackTarget] = useState<GitSync | null>(null);
  const history = useQuery({
    queryKey: ["skill-git-syncs", accessToken, source.source_id],
    queryFn: () => listGitSkillSyncs(accessToken, source.source_id),
    refetchInterval: source.status === "syncing" ? 15_000 : false,
  });
  const decide = useMutation({
    mutationFn: ({ sync, decision }: { sync: GitSync; decision: SyncDecision }) =>
      decideGitSkillSync(accessToken, source.source_id, sync.sync_id, decision),
    onSuccess: (_result, { sync, decision }) => {
      const messages = {
        approve: t("skills.gitSync.toasts.approved"),
        reject: t("skills.gitSync.toasts.rejected"),
        rollback: t("skills.gitSync.toasts.rolledBack", { sha: shortSha(sync.commit_sha) }),
      };
      toast.success(messages[decision]);
      void history.refetch();
      onChanged();
    },
    onError: () => toast.error(t("skills.gitSync.toasts.decisionFailed")),
  });

  const onDecide = (sync: GitSync, decision: SyncDecision) => {
    if (decision === "rollback") {
      setRollbackTarget(sync);
      return;
    }
    decide.mutate({ sync, decision });
  };

  const syncs = history.data?.syncs ?? [];
  return (
    <Sheet open onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle>{t("skills.gitSync.history.title")}</SheetTitle>
          <SheetDescription className="font-mono">
            {t("skills.gitSync.history.description", {
              repository: `${source.owner}/${source.repository}`,
              branch: source.branch,
            })}
          </SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-4">
          {history.isError && (
            <p role="alert" className="text-sm text-destructive">
              {t("skills.gitSync.history.loadFailed")}
            </p>
          )}
          {history.isSuccess && syncs.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("skills.gitSync.history.empty")}</p>
          )}
          <ul className="flex flex-col gap-2">
            {syncs.map((sync) => (
              <SyncRow key={sync.sync_id} sync={sync} source={source} busy={decide.isPending} onDecide={onDecide} />
            ))}
          </ul>
        </div>
      </SheetContent>
      {rollbackTarget && (
        <AlertDialog open onOpenChange={(next) => !next && setRollbackTarget(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {t("skills.gitSync.history.rollbackTitle", { sha: shortSha(rollbackTarget.commit_sha) })}
              </AlertDialogTitle>
              <AlertDialogDescription>{t("skills.gitSync.history.rollbackDescription")}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t("skills.gitSync.history.cancel")}</AlertDialogCancel>
              <Button
                disabled={decide.isPending}
                onClick={() => {
                  decide.mutate({ sync: rollbackTarget, decision: "rollback" });
                  setRollbackTarget(null);
                }}
              >
                {t("skills.gitSync.history.rollbackConfirm")}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </Sheet>
  );
}
