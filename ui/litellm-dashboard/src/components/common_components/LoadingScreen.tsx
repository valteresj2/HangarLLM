import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cva.config";
import { HangarLogo } from "@/components/hangar/HangarLogo";
import { UiLoadingSpinner } from "../ui/ui-loading-spinner";

export default function LoadingScreen() {
  const { t } = useTranslation();
  return (
    <div className={cx("h-screen bg-background", "flex items-center justify-center gap-4")}>
      <div className="border-r border-border py-2 pr-4">
        <HangarLogo markClassName="size-6" />
      </div>

      <div className="flex items-center justify-center gap-2">
        <UiLoadingSpinner className="size-4 text-primary" />
        <span className="text-muted-foreground text-sm">{t("shell.loadingScreen.loading")}</span>
      </div>
    </div>
  );
}
