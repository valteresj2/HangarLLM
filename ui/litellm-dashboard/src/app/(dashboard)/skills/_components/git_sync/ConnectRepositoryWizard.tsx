"use client";

import { skipToken, useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Lock, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import CopyButton from "@/components/shared/CopyButton";
import { StatusBadge } from "@/components/shared/table_cells";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createGitSkillSource, discoverGitBranches, discoverGitRepositories } from "@/components/networking";
import type {
  GitConnection,
  GitRepository,
  GitSourceCreated,
  RepositoryList,
} from "@/components/claude_code_plugins/gitSyncTypes";
import { cn } from "@/lib/cva.config";
import { toast } from "@/lib/toast";

import { SYNC_STATUS_TONE } from "./attention";
import { ConnectionFields, SourceSettingsFields, TextField } from "./FormFields";
import { EMPTY_CONNECTION, connectionPayload, type SettingsDraft } from "./formModel";
import { SyncSummaryText } from "./SyncReportView";
import {
  DEFAULT_SETTINGS,
  canLeaveConnectionStep,
  createPayload,
  effectiveBranch,
  nameForRepository,
  publicRepository,
  type PublicRepoDraft,
  type WizardStep,
} from "./wizardModel";

const MAX_LISTED = 200;

function RepositoryOption({
  repository,
  active,
  onSelect,
}: {
  repository: GitRepository;
  active: boolean;
  onSelect: (repository: GitRepository) => void;
}) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={() => onSelect(repository)}
      className={cn(
        "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted",
        active && "bg-primary/10 text-primary",
      )}
    >
      <span className="flex items-center gap-1.5 truncate font-mono text-xs">
        {repository.private && (
          <Lock className="size-3.5 shrink-0" aria-label={t("skills.gitSync.wizard.privateRepo")} />
        )}
        {repository.full_name}
      </span>
      <span className="shrink-0 text-xs text-muted-foreground">{repository.default_branch}</span>
    </button>
  );
}

function RepositoryPicker({
  list,
  selected,
  onSelect,
}: {
  list: RepositoryList;
  selected: GitRepository | null;
  onSelect: (repository: GitRepository) => void;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const needle = search.trim().toLowerCase();
  const matches = list.repositories
    .filter((repository) => repository.full_name.toLowerCase().includes(needle))
    .slice(0, MAX_LISTED);
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="git-sync-repo-search">{t("skills.gitSync.wizard.repository")}</Label>
      <div className="relative">
        <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
        <Input
          id="git-sync-repo-search"
          className="pl-8"
          placeholder={t("skills.gitSync.wizard.searchRepositories")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <div
        role="listbox"
        aria-label={t("skills.gitSync.wizard.repository")}
        className="max-h-48 overflow-y-auto rounded-md border"
      >
        {matches.length === 0 && (
          <p className="p-3 text-sm text-muted-foreground">{t("skills.gitSync.wizard.noRepositories")}</p>
        )}
        {matches.map((repository) => (
          <RepositoryOption
            key={repository.full_name}
            repository={repository}
            active={selected?.full_name === repository.full_name}
            onSelect={onSelect}
          />
        ))}
      </div>
      {list.truncated && <p className="text-xs text-muted-foreground">{t("skills.gitSync.wizard.truncated")}</p>}
    </div>
  );
}

function BranchSelect({
  branches,
  loading,
  failed,
  value,
  onChange,
}: {
  branches: readonly string[] | undefined;
  loading: boolean;
  failed: boolean;
  value: string;
  onChange: (branch: string) => void;
}) {
  const { t } = useTranslation();
  const options = branches && branches.length > 0 ? branches : [value];
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="git-sync-branch">{t("skills.gitSync.wizard.branch")}</Label>
      <Select
        items={options.map((branch) => ({ value: branch, label: branch }))}
        value={value}
        disabled={loading}
        onValueChange={(next: string | null) => next && onChange(next)}
      >
        <SelectTrigger id="git-sync-branch" className="w-full">
          <SelectValue placeholder={t("skills.gitSync.wizard.loadingBranches")} />
        </SelectTrigger>
        <SelectContent>
          {options.map((branch) => (
            <SelectItem key={branch} value={branch}>
              {branch}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {failed && (
        <p role="alert" className="text-xs text-destructive">
          {t("skills.gitSync.toasts.branchesFailed")}
        </p>
      )}
    </div>
  );
}

function WebhookStep({ created }: { created: GitSourceCreated }) {
  const { t } = useTranslation();
  const rows = [
    { label: t("skills.gitSync.wizard.webhookUrl"), value: created.webhook.url, testId: "webhook-url" },
    { label: t("skills.gitSync.wizard.webhookSecret"), value: created.webhook.secret, testId: "webhook-secret" },
  ];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 text-success">
        <CheckCircle2 className="size-5" />
        <span className="font-medium">{t("skills.gitSync.toasts.created", { name: created.source.name })}</span>
      </div>
      <div className="flex flex-col gap-2 rounded-lg border p-3">
        <h3 className="font-medium">{t("skills.gitSync.wizard.webhookTitle")}</h3>
        <p className="text-sm text-muted-foreground">{t("skills.gitSync.wizard.webhookSteps")}</p>
        {rows.map((row) => (
          <div key={row.testId} className="flex flex-col gap-1">
            <span className="text-xs font-medium">{row.label}</span>
            <div className="flex items-center gap-2 rounded-md bg-muted px-2 py-1.5">
              <code data-testid={row.testId} className="flex-1 truncate text-xs">
                {row.value}
              </code>
              <CopyButton value={row.value} label={t("skills.gitSync.wizard.copy")} />
            </div>
          </div>
        ))}
        <p className="text-xs text-warning">{t("skills.gitSync.wizard.secretOnce")}</p>
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium">{t("skills.gitSync.wizard.firstSync")}</h3>
        {created.sync ? (
          <div className="flex items-center gap-2">
            <StatusBadge
              tone={SYNC_STATUS_TONE[created.sync.status]}
              label={t(`skills.gitSync.syncStatus.${created.sync.status}`)}
            />
            <SyncSummaryText summary={created.sync.report.summary} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{t("skills.gitSync.wizard.noFirstSync")}</p>
        )}
      </div>
    </div>
  );
}

function ConnectionStep({
  connection,
  onConnection,
  publicRepo,
  onPublicRepo,
}: {
  connection: GitConnection;
  onConnection: (connection: GitConnection) => void;
  publicRepo: PublicRepoDraft;
  onPublicRepo: (draft: PublicRepoDraft) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-4">
      <ConnectionFields value={connection} onChange={onConnection} />
      {connection.auth_type === "none" && (
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label={t("skills.gitSync.wizard.publicOwner")}
            value={publicRepo.owner}
            placeholder="anthropics"
            onChange={(owner) => onPublicRepo({ ...publicRepo, owner })}
          />
          <TextField
            label={t("skills.gitSync.wizard.publicRepository")}
            value={publicRepo.name}
            placeholder="skills"
            onChange={(name) => onPublicRepo({ ...publicRepo, name })}
          />
        </div>
      )}
    </div>
  );
}

function useBranches(accessToken: string, connection: GitConnection, repository: GitRepository | null) {
  return useQuery({
    queryKey: ["skill-git-branches", accessToken, connection, repository?.full_name],
    queryFn: repository
      ? () => discoverGitBranches(accessToken, { connection, owner: repository.owner, repository: repository.name })
      : skipToken,
    retry: false,
  });
}

interface ConnectRepositoryWizardProps {
  accessToken: string;
  open: boolean;
  onClose: () => void;
  onCreated: (created: GitSourceCreated) => void;
}

export default function ConnectRepositoryWizard({
  accessToken,
  open,
  onClose,
  onCreated,
}: ConnectRepositoryWizardProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<WizardStep>("connection");
  const [connection, setConnection] = useState<GitConnection>(EMPTY_CONNECTION);
  const [publicRepo, setPublicRepo] = useState<PublicRepoDraft>({ owner: "", name: "" });
  const [repositories, setRepositories] = useState<RepositoryList | null>(null);
  const [selected, setSelected] = useState<GitRepository | null>(null);
  const [pickedBranch, setPickedBranch] = useState<string | null>(null);
  const [settings, setSettings] = useState<SettingsDraft>(DEFAULT_SETTINGS);
  const [created, setCreated] = useState<GitSourceCreated | null>(null);
  const payload = useMemo(() => connectionPayload(connection), [connection]);
  const branches = useBranches(accessToken, payload, step === "repository" ? selected : null);
  const branch = effectiveBranch(pickedBranch, selected, branches.data?.branches);

  const selectRepository = (repository: GitRepository) => {
    setSelected(repository);
    setPickedBranch(null);
    setSettings((current) => ({ ...current, name: nameForRepository(current.name, selected, repository) }));
  };

  const loadRepositories = useMutation({
    mutationFn: () => discoverGitRepositories(accessToken, payload),
    onSuccess: (list) => {
      setRepositories(list);
      setSelected(null);
      setStep("repository");
    },
    onError: () => toast.error(t("skills.gitSync.toasts.reposFailed")),
  });

  const create = useMutation({
    mutationFn: (repository: GitRepository) =>
      createGitSkillSource(accessToken, createPayload(settings, payload, repository, branch)),
    onSuccess: (result) => {
      setCreated(result);
      setStep("done");
      onCreated(result);
    },
    onError: () => toast.error(t("skills.gitSync.toasts.createFailed")),
  });

  const leaveConnectionStep = () => {
    if (connection.auth_type !== "none") {
      loadRepositories.mutate();
      return;
    }
    setRepositories(null);
    selectRepository(publicRepository(publicRepo));
    setStep("repository");
  };

  const stepTitles: Record<WizardStep, string> = {
    connection: t("skills.gitSync.wizard.stepConnection"),
    repository: t("skills.gitSync.wizard.stepRepository"),
    done: t("skills.gitSync.wizard.stepDone"),
  };
  const canLeave = canLeaveConnectionStep(connection, publicRepo) && !loadRepositories.isPending;
  const nextLabel =
    connection.auth_type === "none" ? t("skills.gitSync.wizard.next") : t("skills.gitSync.wizard.loadRepositories");

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("skills.gitSync.wizard.title")}</DialogTitle>
          <DialogDescription data-testid="wizard-step">{stepTitles[step]}</DialogDescription>
        </DialogHeader>

        {step === "connection" && (
          <ConnectionStep
            connection={connection}
            onConnection={setConnection}
            publicRepo={publicRepo}
            onPublicRepo={setPublicRepo}
          />
        )}

        {step === "repository" && (
          <div className="flex flex-col gap-4">
            {repositories ? (
              <RepositoryPicker list={repositories} selected={selected} onSelect={selectRepository} />
            ) : (
              <p className="font-mono text-sm">{selected?.full_name}</p>
            )}
            {selected && (
              <>
                <BranchSelect
                  branches={branches.data?.branches}
                  loading={branches.isLoading}
                  failed={branches.isError}
                  value={branch}
                  onChange={setPickedBranch}
                />
                <SourceSettingsFields value={settings} repository={selected.full_name} onChange={setSettings} />
              </>
            )}
          </div>
        )}

        {step === "done" && created && <WebhookStep created={created} />}

        <DialogFooter>
          {step === "connection" && (
            <>
              <Button variant="outline" onClick={onClose}>
                {t("skills.gitSync.wizard.cancel")}
              </Button>
              <Button disabled={!canLeave} onClick={leaveConnectionStep}>
                {nextLabel}
              </Button>
            </>
          )}
          {step === "repository" && (
            <>
              <Button variant="outline" onClick={() => setStep("connection")}>
                {t("skills.gitSync.wizard.back")}
              </Button>
              <Button disabled={!selected || create.isPending} onClick={() => selected && create.mutate(selected)}>
                {create.isPending ? t("skills.gitSync.wizard.connecting") : t("skills.gitSync.wizard.connect")}
              </Button>
            </>
          )}
          {step === "done" && <Button onClick={onClose}>{t("skills.gitSync.wizard.close")}</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
