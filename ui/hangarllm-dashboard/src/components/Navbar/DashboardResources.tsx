"use client";

import type { ParseKeys } from "i18next";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { BookOpen, ScrollText } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/cva.config";

type ResourceLink = { href: string; label: ParseKeys; Icon: typeof BookOpen };

const DOCS: readonly ResourceLink[] = [
  { href: "https://github.com/valteresj2/HangarLLM#readme", label: "shell.dashboardResources.links.docs", Icon: BookOpen },
  { href: "https://github.com/valteresj2/HangarLLM#readme", label: "shell.dashboardResources.links.releases", Icon: ScrollText },
];

export function DashboardResources({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="border-t border-border bg-muted/25 p-2">
      <nav aria-label={t("shell.dashboardResources.helpAndResources")} className="grid grid-cols-2 gap-1">
        {DOCS.map(({ href, label, Icon }) => (
          <a
            key={label}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "justify-start gap-2 text-xs font-normal text-muted-foreground",
            )}
          >
            <Icon />
            {t(label)}
          </a>
        ))}
      </nav>
      {children}
    </div>
  );
}
