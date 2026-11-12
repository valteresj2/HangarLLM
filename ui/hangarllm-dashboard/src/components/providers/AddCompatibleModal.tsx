"use client";

import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { credentialsKeys } from "@/app/(dashboard)/hooks/credentials/useCredentials";
import { credentialCreateCall, modelCreateCall, type CompatibleKind } from "@/components/networking";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { extractProxyErrorMessage } from "@/lib/http/client";
import { toast } from "@/lib/toast";

const VENDOR_PROVIDER: Readonly<Record<CompatibleKind, string>> = { openai: "OpenAI", anthropic: "Anthropic" };

export interface CompatibleEndpointValues {
  displayName: string;
  apiBase: string;
  apiKey: string;
  modelNames: string;
}

const slug = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

export const parseModelNames = (value: string): string[] =>
  Array.from(new Set(value.split(/[\s,]+/).filter((name) => name !== "")));

export const buildCompatibleCredential = (kind: CompatibleKind, values: CompatibleEndpointValues) => ({
  credential_name: `${kind}-compatible-${slug(values.displayName)}`,
  display_name: values.displayName.trim(),
  credential_values: {
    api_base: values.apiBase.trim(),
    ...(values.apiKey.trim() ? { api_key: values.apiKey.trim() } : {}),
  },
  credential_info: { custom_llm_provider: VENDOR_PROVIDER[kind], compatible: kind },
});

const EMPTY_VALUES: CompatibleEndpointValues = { displayName: "", apiBase: "", apiKey: "", modelNames: "" };

interface AddCompatibleModalProps {
  kind: CompatibleKind;
  open: boolean;
  onClose: () => void;
}

export default function AddCompatibleModal({ kind, open, onClose }: AddCompatibleModalProps) {
  const { t } = useTranslation();
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();
  const [values, setValues] = useState<CompatibleEndpointValues>(EMPTY_VALUES);
  const [submitted, setSubmitted] = useState(false);
  const [saving, setSaving] = useState(false);

  const missingName = slug(values.displayName) === "";
  const missingBase = values.apiBase.trim() === "";
  const field = (key: keyof CompatibleEndpointValues) => ({
    value: values[key],
    onChange: (event: { target: { value: string } }) =>
      setValues((current) => ({ ...current, [key]: event.target.value })),
  });

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitted(true);
    if (missingName || missingBase) return;
    const credential = buildCompatibleCredential(kind, values);
    const token = accessToken ?? "";
    setSaving(true);
    try {
      await credentialCreateCall(token, credential);
      await Promise.all(
        parseModelNames(values.modelNames).map((name) =>
          modelCreateCall(token, {
            model_name: name,
            hangarllm_params: {
              model: `${kind}/${name}`,
              custom_llm_provider: kind,
              hangarllm_credential_name: credential.credential_name,
            },
            model_info: {},
          }),
        ),
      );
      toast.success(t("modelsAndEndpoints.addCompatibleModal.saved", { name: credential.display_name }));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: credentialsKeys.all }),
        queryClient.invalidateQueries({ queryKey: ["models", "list"] }),
      ]);
      onClose();
    } catch (error) {
      toast.error(extractProxyErrorMessage(error));
    }
    setSaving(false);
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{t(`modelsAndEndpoints.addCompatibleModal.title.${kind}`)}</DialogTitle>
        </DialogHeader>
        <form noValidate onSubmit={(event) => void save(event)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="compatible-display-name">{t("modelsAndEndpoints.addCompatibleModal.displayName")}</Label>
            <Input
              id="compatible-display-name"
              aria-invalid={submitted && missingName}
              aria-describedby={submitted && missingName ? "compatible-display-name-error" : undefined}
              {...field("displayName")}
            />
            {submitted && missingName && (
              <p id="compatible-display-name-error" className="text-xs text-destructive">
                {t("modelsAndEndpoints.addCompatibleModal.displayNameRequired")}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="compatible-api-base">{t("modelsAndEndpoints.addCompatibleModal.apiBase")}</Label>
            <Input
              id="compatible-api-base"
              type="url"
              placeholder="https://"
              aria-invalid={submitted && missingBase}
              aria-describedby={submitted && missingBase ? "compatible-api-base-error" : undefined}
              {...field("apiBase")}
            />
            {submitted && missingBase && (
              <p id="compatible-api-base-error" className="text-xs text-destructive">
                {t("modelsAndEndpoints.addCompatibleModal.apiBaseRequired")}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="compatible-api-key">{t("modelsAndEndpoints.addCompatibleModal.apiKey")}</Label>
            <Input id="compatible-api-key" type="password" autoComplete="off" {...field("apiKey")} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="compatible-models">{t("modelsAndEndpoints.addCompatibleModal.modelNames")}</Label>
            <Textarea id="compatible-models" rows={3} {...field("modelNames")} />
            <p className="text-xs text-muted-foreground">{t("modelsAndEndpoints.addCompatibleModal.modelNamesHint")}</p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              {t("modelsAndEndpoints.addCompatibleModal.cancel")}
            </Button>
            <Button type="submit" disabled={saving}>
              {t("modelsAndEndpoints.addCompatibleModal.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
