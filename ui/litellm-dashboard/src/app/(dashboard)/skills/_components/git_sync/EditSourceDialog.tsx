"use client";

import { useMutation } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { updateGitSkillSource } from "@/components/networking";
import type { GitConnection, GitSource } from "@/components/claude_code_plugins/gitSyncTypes";
import { toast } from "@/lib/toast";

import { ConnectionFields, SourceSettingsFields, TextField } from "./FormFields";
import { connectionComplete, connectionPayload, type SettingsDraft } from "./formModel";
import { connectionOf, settingsOf, updatePayload } from "./wizardModel";

interface EditSourceDialogProps {
  accessToken: string;
  source: GitSource;
  onClose: () => void;
  onSaved: () => void;
}

export default function EditSourceDialog({ accessToken, source, onClose, onSaved }: EditSourceDialogProps) {
  const { t } = useTranslation();
  const replaceId = useId();
  const [settings, setSettings] = useState<SettingsDraft>(() => settingsOf(source));
  const [branch, setBranch] = useState(source.branch);
  const [replaceCredentials, setReplaceCredentials] = useState(false);
  const [connection, setConnection] = useState<GitConnection>(() => connectionOf(source));

  const save = useMutation({
    mutationFn: () =>
      updateGitSkillSource(
        accessToken,
        source.source_id,
        updatePayload(source, settings, branch, replaceCredentials ? connectionPayload(connection) : null),
      ),
    onSuccess: (updated) => {
      toast.success(t("skills.gitSync.toasts.updated", { name: updated.name }));
      onSaved();
      onClose();
    },
    onError: () => toast.error(t("skills.gitSync.toasts.updateFailed")),
  });

  const valid = !replaceCredentials || connectionComplete(connection);

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("skills.gitSync.edit.title", { name: source.name })}</DialogTitle>
          <DialogDescription className="font-mono">
            {source.owner}/{source.repository}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <TextField label={t("skills.gitSync.wizard.branch")} value={branch} onChange={setBranch} />
          <SourceSettingsFields
            value={settings}
            repository={`${source.owner}/${source.repository}`}
            onChange={setSettings}
          />
          <div className="flex flex-col gap-2 rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <Checkbox
                id={replaceId}
                checked={replaceCredentials}
                onCheckedChange={(checked) => setReplaceCredentials(checked === true)}
              />
              <Label htmlFor={replaceId}>{t("skills.gitSync.edit.replaceCredentials")}</Label>
            </div>
            {replaceCredentials ? (
              <ConnectionFields value={connection} onChange={setConnection} />
            ) : (
              <p className="text-xs text-muted-foreground">{t("skills.gitSync.edit.credentialsKept")}</p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("skills.gitSync.wizard.cancel")}
          </Button>
          <Button disabled={!valid || save.isPending} onClick={() => save.mutate()}>
            {t("skills.gitSync.edit.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
