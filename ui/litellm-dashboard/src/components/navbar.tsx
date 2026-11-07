import { useHealthReadinessDetails } from "@/app/(dashboard)/hooks/healthReadiness/useHealthReadinessDetails";
import { useWorker } from "@/hooks/useWorker";
import { uiHref } from "@/utils/uiHref";
import { useTheme } from "@/contexts/ThemeContext";
import { revokeSessionAndClearClientState, useLogout } from "@/app/(dashboard)/hooks/useLogout";
import { getLoginUrl } from "@/utils/returnUrlUtils";
import { Badge } from "@/components/ui/badge";
import { HangarLogo } from "@/components/hangar/HangarLogo";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import React from "react";
import { useTranslation } from "react-i18next";
import { DocsLink } from "./Navbar/DocsLink/DocsLink";
import { cn } from "@/lib/cva.config";
import { NotificationsBell } from "./Navbar/NotificationsBell/NotificationsBell";
import UserDropdown from "./Navbar/UserDropdown/UserDropdown";
import ThemeToggle from "./ThemeToggle/ThemeToggle";
import ViewSwitcher from "./Navbar/ViewSwitcher";
import WorkerDropdown from "./Navbar/WorkerDropdown/WorkerDropdown";

interface NavbarProps {
  accessToken: string | null;
  isPublicPage: boolean;
  sidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
  deploymentHealth?: React.ReactNode;
  deploymentHealthLink?: React.ReactNode;
  publicNavigation?: React.ReactNode;
}

const NAV_LOGO_CLASS_NAME = "h-auto max-h-full w-auto max-w-full object-contain";

const Navbar: React.FC<NavbarProps> = ({
  accessToken,
  isPublicPage = false,
  sidebarCollapsed = false,
  onToggleSidebar,
  deploymentHealth,
  deploymentHealthLink,
  publicNavigation,
}) => {
  const { t } = useTranslation();
  const { logoUrl, logoUrlDark } = useTheme();
  const { data: healthData } = useHealthReadinessDetails(accessToken);
  const version = healthData?.litellm_version;
  const { isControlPlane, selectedWorker } = useWorker();
  const showWorkerSwitch = isControlPlane && selectedWorker !== null;

  const darkImageUrl = logoUrlDark || logoUrl;

  const handleLogout = useLogout(accessToken);

  const handleWorkerSwitch = (workerId: string) => {
    void revokeSessionAndClearClientState(accessToken).finally(() => {
      window.location.href = `${getLoginUrl()}?worker=${encodeURIComponent(workerId)}`;
    });
  };

  return (
    <nav className="sticky top-0 z-chrome border-b border-border bg-card">
      <div className="w-full">
        <div className={cn("flex h-14 items-center px-4", isPublicPage && "gap-4 sm:px-6")}>
          <div className="flex shrink-0 items-center">
            {onToggleSidebar && (
              <button
                onClick={onToggleSidebar}
                className="mr-2 flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                title={sidebarCollapsed ? t("shell.navbar.expandSidebar") : t("shell.navbar.collapseSidebar")}
              >
                <span className="text-lg">
                  {sidebarCollapsed ? (
                    <PanelLeftOpen className="size-[18px]" />
                  ) : (
                    <PanelLeftClose className="size-[18px]" />
                  )}
                </span>
              </button>
            )}

            <div className="flex items-center gap-2">
              <Link href={uiHref("")} className="flex items-center">
                <div className="relative">
                  <div
                    className={cn(
                      "flex h-10 max-w-48 items-center justify-center overflow-hidden",
                      isPublicPage && "h-8 max-w-36 sm:h-10 sm:max-w-48",
                    )}
                  >
                    {logoUrl ? (
                      <>
                        <img
                          src={logoUrl}
                          alt={t("shell.navbar.logoAlt")}
                          className={cn(NAV_LOGO_CLASS_NAME, "dark:hidden")}
                        />
                        <img
                          src={darkImageUrl ?? logoUrl}
                          alt=""
                          aria-hidden
                          className={cn(NAV_LOGO_CLASS_NAME, "hidden dark:block")}
                        />
                      </>
                    ) : (
                      <HangarLogo markClassName="size-7" />
                    )}
                  </div>
                </div>
              </Link>
              {version && (
                <div className="relative">
                  <Badge variant="outline" className="relative z-raised cursor-pointer text-xs font-medium">
                    <a
                      href="https://docs.litellm.ai/release_notes"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0"
                    >
                      v{version}
                    </a>
                  </Badge>
                </div>
              )}
            </div>
          </div>

          {publicNavigation}

          {!isPublicPage && (
            <div className="ml-4 flex shrink-0 items-center border-l border-border pl-4">
              <ViewSwitcher />
            </div>
          )}

          <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-4">
            {showWorkerSwitch && (
              <div className="flex shrink-0 items-center">
                <WorkerDropdown onWorkerSwitch={handleWorkerSwitch} />
              </div>
            )}

            <nav
              aria-label={t("shell.navbar.productDocs")}
              className={`flex min-w-0 items-center gap-2 ${showWorkerSwitch ? "border-l border-border pl-4" : ""}`}
            >
              <DocsLink />
            </nav>

            {!isPublicPage && (
              <div className="flex shrink-0 items-center border-l border-border pl-4">
                <div className="flex items-center gap-0.5 rounded-lg bg-muted px-1 py-0 transition-colors hover:bg-accent">
                  <ThemeToggle />
                  <span className="mx-0.5 h-6 w-px shrink-0 bg-border" aria-hidden />
                  {deploymentHealth}
                  <NotificationsBell accessToken={accessToken} deploymentHealthLink={deploymentHealthLink} />
                  <span className="mx-0.5 h-6 w-px shrink-0 bg-border" aria-hidden />
                  <UserDropdown onLogout={handleLogout} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
