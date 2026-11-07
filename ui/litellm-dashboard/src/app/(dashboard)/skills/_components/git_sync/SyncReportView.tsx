"use client";

import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import { useTranslation } from "react-i18next";

import { StatusBadge } from "@/components/shared/table_cells";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { IssueSeverity, SyncIssue, SyncReport, SyncSummary } from "@/components/claude_code_plugins/gitSyncTypes";
import { cn } from "@/lib/cva.config";

import { SKILL_ACTION_TONE } from "./attention";

const SEVERITY_ICON: Record<IssueSeverity, typeof Info> = { info: Info, warning: AlertTriangle, error: AlertCircle };
const SEVERITY_CLASS: Record<IssueSeverity, string> = {
  info: "text-info",
  warning: "text-warning",
  error: "text-destructive",
};

export function SyncSummaryText({ summary }: { summary: SyncSummary }) {
  const { t } = useTranslation();
  return <span className="text-xs text-muted-foreground">{t("skills.gitSync.history.summary", { ...summary })}</span>;
}

export function IssueList({ issues }: { issues: readonly SyncIssue[] }) {
  const { t } = useTranslation();
  if (issues.length === 0)
    return <span className="text-xs text-muted-foreground">{t("skills.gitSync.history.noIssues")}</span>;
  return (
    <ul className="flex flex-col gap-1">
      {issues.map((issue, index) => {
        const Icon = SEVERITY_ICON[issue.severity];
        return (
          <li key={`${issue.code}-${index}`} className="flex items-start gap-1.5 text-xs">
            <Icon
              className={cn("mt-0.5 size-3.5 shrink-0", SEVERITY_CLASS[issue.severity])}
              aria-label={t(`skills.gitSync.severity.${issue.severity}`)}
            />
            <span>
              {issue.message}
              {issue.file && <code className="ml-1 text-muted-foreground">{issue.file}</code>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export default function SyncReportView({ report }: { report: SyncReport }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      {report.error && (
        <p role="alert" className="text-sm text-destructive">
          {t("skills.gitSync.history.error", { message: report.error })}
        </p>
      )}
      {report.issues.length > 0 && (
        <div className="flex flex-col gap-1">
          <h4 className="text-xs font-semibold uppercase text-muted-foreground">
            {t("skills.gitSync.history.globalIssues")}
          </h4>
          <IssueList issues={report.issues} />
        </div>
      )}
      {report.skills.length > 0 && (
        <div className="flex flex-col gap-1">
          <h4 className="text-xs font-semibold uppercase text-muted-foreground">
            {t("skills.gitSync.history.skillsHeader")}
          </h4>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("skills.gitSync.history.colSkill")}</TableHead>
                <TableHead>{t("skills.gitSync.history.colPath")}</TableHead>
                <TableHead>{t("skills.gitSync.history.colAction")}</TableHead>
                <TableHead>{t("skills.gitSync.history.colVersion")}</TableHead>
                <TableHead>{t("skills.gitSync.history.colIssues")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.skills.map((skill) => (
                <TableRow key={skill.path}>
                  <TableCell className="font-mono text-xs">{skill.name ?? "—"}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{skill.path || "/"}</TableCell>
                  <TableCell>
                    <StatusBadge
                      tone={SKILL_ACTION_TONE[skill.action]}
                      label={t(`skills.gitSync.action.${skill.action}`)}
                    />
                  </TableCell>
                  <TableCell className="text-xs">{skill.version ?? "—"}</TableCell>
                  <TableCell className="max-w-md whitespace-normal">
                    <IssueList issues={skill.issues} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
