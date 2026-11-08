import React from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  formatGuardrailMode,
  formatLoggingOnlyScope,
  loggingOnlyContinueFromParams,
  modeIncludesLoggingOnly,
} from "./guardrail_info_helpers";

type GuardrailModeParams = {
  mode?: unknown;
  default_on?: boolean;
  logging_only_scope?: string | null;
  logging_only_continue_on_input_failure?: boolean | null;
};

export const GuardrailModeCard: React.FC<{ hangarllmParams: GuardrailModeParams }> = ({ hangarllmParams }) => {
  const { t } = useTranslation();
  return (
    <Card className="block p-6">
      <p>{t("guardrails.modeDisplay.mode")}</p>
      <div className="mt-2">
        <h3 className="text-lg font-medium">{formatGuardrailMode(hangarllmParams.mode) || "-"}</h3>
        <Badge variant={hangarllmParams.default_on ? "secondary" : "outline"}>
          {hangarllmParams.default_on ? t("guardrails.modeDisplay.defaultOn") : t("guardrails.modeDisplay.defaultOff")}
        </Badge>
      </div>
      {modeIncludesLoggingOnly(hangarllmParams.mode) && (
        <div className="mt-4">
          <p>{t("guardrails.modeDisplay.loggingOnlyScope")}</p>
          <h3 className="text-lg font-medium">{formatLoggingOnlyScope(hangarllmParams.logging_only_scope, t)}</h3>
          <p className="mt-2">{t("guardrails.modeDisplay.continueAfterFlagged")}</p>
          <h3 className="text-lg font-medium">
            {loggingOnlyContinueFromParams(hangarllmParams)
              ? t("guardrails.modeDisplay.on")
              : t("guardrails.modeDisplay.off")}
          </h3>
        </div>
      )}
    </Card>
  );
};

export const GuardrailModeRows: React.FC<{ hangarllmParams: GuardrailModeParams }> = ({ hangarllmParams }) => {
  const { t } = useTranslation();
  return (
    <>
      <div>
        <p className="font-medium">{t("guardrails.modeDisplay.mode")}</p>
        <div>{formatGuardrailMode(hangarllmParams.mode) || "-"}</div>
      </div>
      {modeIncludesLoggingOnly(hangarllmParams.mode) && (
        <div>
          <p className="font-medium">{t("guardrails.modeDisplay.loggingOnlyScope")}</p>
          <div>{formatLoggingOnlyScope(hangarllmParams.logging_only_scope, t)}</div>
          <p className="font-medium">{t("guardrails.modeDisplay.continueAfterFlagged")}</p>
          <div>
            {loggingOnlyContinueFromParams(hangarllmParams)
              ? t("guardrails.modeDisplay.on")
              : t("guardrails.modeDisplay.off")}
          </div>
        </div>
      )}
    </>
  );
};
