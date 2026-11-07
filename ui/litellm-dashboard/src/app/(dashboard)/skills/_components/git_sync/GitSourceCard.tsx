"use client";

import { formatDistanceToNow } from "date-fns";
import { FolderGit2, History, KeyRound, MoreHorizontal, Pencil, RefreshCw, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { StatusBadge } from "@/components/shared/table_cells";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { GitSource } from "@/components/claude_code_plugins/gitSyncTypes";
import { cn } from "@/lib/cva.config";

import { SOURCE_STATUS_TONE, commitUrl, shortSha } from "./attention";

export type SourceAction = "sync" | "history" | "edit" | "rotate" | "delete";

interface GitSourceCardProps {
  source: GitSource;
  syncing: boolean;
  onAction: (action: SourceAction, source: GitSource) => void;
}

export default function GitSourceCard({ source, syncing, onAction }: GitSourceCardProps) {
  const { t } = useTranslation();
  const busy = syncing || source.status === "syncing";
  const quarantined = source.quarantined_skills.length;
  return (
    <Card data-testid={`git-source-${source.source_id}`}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FolderGit2 className="size-4 text-primary" />
          {source.name}
          <StatusBadge
            tone={SOURCE_STATUS_TONE[source.status]}
            label={t(`skills.gitSync.status.${source.status}`)}
            tooltip={source.status_message ?? undefined}
          />
        </CardTitle>
        <CardDescription className="font-mono text-xs">
          <a
            href={source.repository_url}
            target="_blank"
            rel="noreferrer"
            className="hover:text-primary hover:underline"
          >
            {source.owner}/{source.repository}@{source.branch}
          </a>
          <span className="text-muted-foreground"> / {source.skills_path || t("skills.gitSync.card.rootFolder")}</span>
        </CardDescription>
        <CardAction className="flex items-center gap-1">
          <Button size="sm" variant="outline" disabled={busy} onClick={() => onAction("sync", source)}>
            <RefreshCw className={cn("size-3.5", busy && "animate-spin")} />
            {t("skills.gitSync.actions.syncNow")}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onAction("history", source)}>
            <History className="size-3.5" />
            {t("skills.gitSync.actions.history")}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger
              aria-label={t("skills.gitSync.actions.menu")}
              className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }), "text-muted-foreground")}
            >
              <MoreHorizontal className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem onClick={() => onAction("edit", source)}>
                <Pencil />
                {t("skills.gitSync.actions.edit")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAction("rotate", source)}>
                <KeyRound />
                {t("skills.gitSync.actions.rotateSecret")}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => onAction("delete", source)}>
                <Trash2 />
                {t("skills.gitSync.actions.delete")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            {source.scope === "all_keys"
              ? t("skills.gitSync.card.scopeAllKeys")
              : t("skills.gitSync.card.scopeAccessGroup", { name: source.access_group_name ?? "" })}
          </Badge>
          <Badge variant="outline">
            {source.publish_mode === "auto" ? t("skills.gitSync.card.modeAuto") : t("skills.gitSync.card.modeApproval")}
          </Badge>
          <Badge variant="outline">
            {source.auto_sync
              ? t("skills.gitSync.card.autoSyncEvery", { minutes: Math.round(source.poll_interval_seconds / 60) })
              : t("skills.gitSync.card.autoSyncOff")}
          </Badge>
          <span className="text-muted-foreground">
            {t("skills.gitSync.card.managed", { count: source.managed_skills.length })}
          </span>
          {quarantined > 0 && (
            <StatusBadge
              tone="error"
              label={t("skills.gitSync.card.quarantined", { count: quarantined })}
              tooltip={source.quarantined_skills.join(", ")}
            />
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>
            {source.last_synced_at
              ? t("skills.gitSync.card.lastSync", {
                  when: formatDistanceToNow(new Date(source.last_synced_at), { addSuffix: true }),
                })
              : t("skills.gitSync.card.neverSynced")}
          </span>
          {source.applied_sha && (
            <span>
              {t("skills.gitSync.card.applied")}{" "}
              <a
                href={commitUrl(source.repository_url, source.applied_sha)}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-primary hover:underline"
              >
                {shortSha(source.applied_sha)}
              </a>
            </span>
          )}
        </div>
        {source.status_message && source.status !== "healthy" && (
          <p className={cn("text-xs", source.status === "failed" ? "text-destructive" : "text-warning")}>
            {source.status_message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
