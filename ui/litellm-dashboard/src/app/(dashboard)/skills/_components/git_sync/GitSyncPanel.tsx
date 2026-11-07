"use client";

import { useMutation } from "@tanstack/react-query";
import { FolderGit2, Plus } from "lucide-react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import CopyButton from "@/components/shared/CopyButton";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { deleteGitSkillSource, rotateGitSkillWebhookSecret, syncGitSkillSource } from "@/components/networking";
import type { GitSource, WebhookSetup } from "@/components/claude_code_plugins/gitSyncTypes";
import { toast } from "@/lib/toast";

import ConnectRepositoryWizard from "./ConnectRepositoryWizard";
import EditSourceDialog from "./EditSourceDialog";
import GitSourceCard, { type SourceAction } from "./GitSourceCard";
import SyncHistorySheet from "./SyncHistorySheet";

interface GitSyncPanelProps {
  accessToken: string;
  sources: readonly GitSource[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  onChanged: () => void;
}

function DeleteSourceDialog({
  source,
  busy,
  onCancel,
  onConfirm,
}: {
  source: GitSource;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (unpublish: boolean) => void;
}) {
  const { t } = useTranslation();
  const checkboxId = useId();
  const [unpublish, setUnpublish] = useState(false);
  return (
    <AlertDialog open onOpenChange={(next) => !next && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("skills.gitSync.deleteDialog.title")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("skills.gitSync.deleteDialog.description", { name: source.name })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex items-center gap-2">
          <Checkbox id={checkboxId} checked={unpublish} onCheckedChange={(checked) => setUnpublish(checked === true)} />
          <Label htmlFor={checkboxId}>{t("skills.gitSync.deleteDialog.unpublish")}</Label>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>{t("skills.gitSync.deleteDialog.cancel")}</AlertDialogCancel>
          <Button variant="destructive" disabled={busy} onClick={() => onConfirm(unpublish)}>
            {t("skills.gitSync.deleteDialog.confirm")}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function RotatedSecretDialog({ webhook, onClose }: { webhook: WebhookSetup; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <AlertDialog open onOpenChange={(next) => !next && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("skills.gitSync.rotateDialog.title")}</AlertDialogTitle>
          <AlertDialogDescription>{t("skills.gitSync.rotateDialog.description")}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex items-center gap-2 rounded-md bg-muted px-2 py-1.5">
          <code className="flex-1 truncate text-xs">{webhook.secret}</code>
          <CopyButton value={webhook.secret} label={t("skills.gitSync.wizard.copy")} />
        </div>
        <AlertDialogFooter>
          <Button onClick={onClose}>{t("skills.gitSync.rotateDialog.close")}</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default function GitSyncPanel({
  accessToken,
  sources,
  isLoading,
  isError,
  onRetry,
  onChanged,
}: GitSyncPanelProps) {
  const { t } = useTranslation();
  const [wizardOpen, setWizardOpen] = useState(false);
  const [editing, setEditing] = useState<GitSource | null>(null);
  const [historyFor, setHistoryFor] = useState<GitSource | null>(null);
  const [deleting, setDeleting] = useState<GitSource | null>(null);
  const [rotated, setRotated] = useState<WebhookSetup | null>(null);

  const sync = useMutation({
    mutationFn: (source: GitSource) => syncGitSkillSource(accessToken, source.source_id),
    onSuccess: (result, source) => {
      if (result.status === "failed") toast.error(t("skills.gitSync.toasts.syncFailed", { name: source.name }));
      else toast.success(t("skills.gitSync.toasts.syncDone", { name: source.name }));
      onChanged();
    },
    onError: (_error, source) => toast.error(t("skills.gitSync.toasts.syncFailed", { name: source.name })),
  });

  const rotate = useMutation({
    mutationFn: (source: GitSource) => rotateGitSkillWebhookSecret(accessToken, source.source_id),
    onSuccess: setRotated,
    onError: () => toast.error(t("skills.gitSync.toasts.rotateFailed")),
  });

  const remove = useMutation({
    mutationFn: ({ source, unpublish }: { source: GitSource; unpublish: boolean }) =>
      deleteGitSkillSource(accessToken, source.source_id, unpublish),
    onSuccess: (_result, { source }) => {
      toast.success(t("skills.gitSync.toasts.deleted", { name: source.name }));
      setDeleting(null);
      onChanged();
    },
    onError: () => toast.error(t("skills.gitSync.toasts.deleteFailed")),
  });

  const onAction = (action: SourceAction, source: GitSource) => {
    switch (action) {
      case "sync":
        sync.mutate(source);
        return;
      case "history":
        setHistoryFor(source);
        return;
      case "edit":
        setEditing(source);
        return;
      case "rotate":
        rotate.mutate(source);
        return;
      case "delete":
        setDeleting(source);
        return;
    }
  };

  const showEmpty = !isLoading && !isError && sources.length === 0;
  const currentHistorySource = historyFor
    ? sources.find((source) => source.source_id === historyFor.source_id) ?? historyFor
    : null;

  return (
    <div className="my-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-3xl text-sm text-muted-foreground">{t("skills.gitSync.intro")}</p>
        <Button onClick={() => setWizardOpen(true)}>
          <Plus className="size-4" />
          {t("skills.gitSync.connectButton")}
        </Button>
      </div>

      {isError && (
        <div role="alert" className="text-sm text-destructive">
          {t("skills.gitSync.loadFailed")}
          <Button variant="link" onClick={onRetry}>
            {t("skills.gitSync.retry")}
          </Button>
        </div>
      )}

      {showEmpty && (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-10 text-center">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
            <FolderGit2 className="size-5 text-primary" />
          </div>
          <div className="text-sm font-medium">{t("skills.gitSync.empty.title")}</div>
          <p className="max-w-md text-sm text-muted-foreground">{t("skills.gitSync.empty.description")}</p>
          <Button className="mt-2" onClick={() => setWizardOpen(true)}>
            {t("skills.gitSync.connectButton")}
          </Button>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {sources.map((source) => (
          <GitSourceCard
            key={source.source_id}
            source={source}
            syncing={sync.isPending && sync.variables?.source_id === source.source_id}
            onAction={onAction}
          />
        ))}
      </div>

      {wizardOpen && (
        <ConnectRepositoryWizard
          accessToken={accessToken}
          open
          onClose={() => setWizardOpen(false)}
          onCreated={onChanged}
        />
      )}
      {editing && (
        <EditSourceDialog
          accessToken={accessToken}
          source={editing}
          onClose={() => setEditing(null)}
          onSaved={onChanged}
        />
      )}
      {currentHistorySource && (
        <SyncHistorySheet
          accessToken={accessToken}
          source={currentHistorySource}
          onClose={() => setHistoryFor(null)}
          onChanged={onChanged}
        />
      )}
      {deleting && (
        <DeleteSourceDialog
          source={deleting}
          busy={remove.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={(unpublish) => remove.mutate({ source: deleting, unpublish })}
        />
      )}
      {rotated && <RotatedSecretDialog webhook={rotated} onClose={() => setRotated(null)} />}
    </div>
  );
}
