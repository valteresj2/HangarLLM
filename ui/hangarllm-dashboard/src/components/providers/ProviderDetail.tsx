"use client";

import { useState } from "react";
import { parseAsString, useQueryStates } from "nuqs";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Pencil, Plus, Trash2 } from "lucide-react";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { credentialsKeys } from "@/app/(dashboard)/hooks/credentials/useCredentials";
import { useLatestModelHealth, useRecordCredentialTests } from "@/app/(dashboard)/hooks/providers/useProviderHealth";
import { PREFILL_URL_PARAMS } from "@/app/(dashboard)/models-and-endpoints/addModelPrefill";
import DeleteResourceModal from "@/components/common_components/DeleteResourceModal";
import CredentialModal from "@/components/model_add/CredentialModal";
import { buildCredential, type CredentialSubmission } from "@/components/model_add/credential_form_helpers";
import { Logo } from "@/components/molecules/logo/Logo";
import {
  credentialCreateCall,
  credentialDeleteCall,
  credentialTestCall,
  credentialUpdateCall,
  modelOrderUpdateCall,
  type CredentialItem,
  type CredentialTestResult,
} from "@/components/networking";
import { Alert, AlertDescription } from "@/components/shared/Alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { extractProxyErrorMessage } from "@/lib/http/client";
import { toast } from "@/lib/toast";
import { stripMaskedSecrets } from "@/utils/maskedSecretUtils";
import type { ProviderCard, ProviderModel, TestResultsByName } from "./providerCards";

const TEST_MODEL_REQUIRED = "test model required";
const MODEL_LIST_ID = "provider-detail-models";

const ADD_MODEL_URL_PARAMS = { tab: parseAsString, provider_detail: parseAsString, ...PREFILL_URL_PARAMS };

const needsTestModel = (result: CredentialTestResult | undefined): boolean =>
  result?.status === "untested" && result.error === TEST_MODEL_REQUIRED;

type AddState =
  | { kind: "idle" }
  | { kind: "testing" }
  | { kind: "failed"; submission: CredentialSubmission; message: string }
  | { kind: "needs_model"; submission: CredentialSubmission };

function TestResultSummary({ result }: { result: CredentialTestResult | undefined }) {
  const { t } = useTranslation();
  if (result === undefined || result.status === "untested") {
    return <Badge variant="outline">{t("modelsAndEndpoints.providerDetail.result.untested")}</Badge>;
  }
  const failing = result.status === "failing";
  return (
    <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <Badge variant={failing ? "destructive" : "secondary"} className={failing ? undefined : "text-success"}>
        {failing
          ? t("modelsAndEndpoints.providerDetail.result.failing", {
              reason: result.http_status ?? result.error ?? "",
            })
          : t("modelsAndEndpoints.providerDetail.result.healthy")}
      </Badge>
      {result.kind !== null && <span>{t(`modelsAndEndpoints.providerDetail.kind.${result.kind}`)}</span>}
      {result.latency_ms !== null && (
        <span>{t("modelsAndEndpoints.providerDetail.latency", { latency: Math.round(result.latency_ms) })}</span>
      )}
      {result.checked_at !== null && <span>{new Date(result.checked_at).toLocaleString()}</span>}
      {failing && result.error && <span className="text-destructive">{result.error}</span>}
    </span>
  );
}

interface TestModelPickerProps {
  id: string;
  value: string;
  placeholder: string | null;
  onChange: (value: string) => void;
}

function TestModelPicker({ id, value, placeholder, onChange }: TestModelPickerProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{t("modelsAndEndpoints.providerDetail.testModel")}</Label>
      <Input
        id={id}
        list={MODEL_LIST_ID}
        value={value}
        placeholder={placeholder ?? undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function OrderInput({ model }: { model: ProviderModel }) {
  const { t } = useTranslation();
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();
  const stored = model.hangarllm_params?.order ?? null;
  const [value, setValue] = useState(stored === null ? "" : String(stored));
  const modelId = model.model_info?.id ?? null;
  const label = t("modelsAndEndpoints.providerDetail.orderFor", { model: model.model_name ?? "" });

  if (modelId === null || model.model_info?.db_model === false) {
    return <span aria-label={label}>{stored ?? "-"}</span>;
  }

  const commit = async () => {
    const order = Number(value);
    if (!Number.isInteger(order) || order < 1 || order === stored) {
      setValue(stored === null ? "" : String(stored));
      return;
    }
    try {
      await modelOrderUpdateCall(accessToken ?? "", modelId, order);
      toast.success(t("modelsAndEndpoints.providerDetail.orderUpdated"));
      await queryClient.invalidateQueries({ queryKey: ["models", "list"] });
    } catch (error) {
      toast.error(extractProxyErrorMessage(error));
    }
  };

  return (
    <Input
      type="number"
      min={1}
      aria-label={label}
      className="h-8 w-20"
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onBlur={() => void commit()}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
    />
  );
}

interface ProviderDetailProps {
  card: ProviderCard;
  results: TestResultsByName;
  onBack: () => void;
}

export default function ProviderDetail({ card, results, onBack }: ProviderDetailProps) {
  const { t } = useTranslation();
  const { accessToken } = useAuthorized();
  const queryClient = useQueryClient();
  const recordTests = useRecordCredentialTests();
  const modelHealth = useLatestModelHealth();
  const [, setUrl] = useQueryStates(ADD_MODEL_URL_PARAMS);
  const { entry, credentials, models } = card;
  const isCompatible = entry.compatibleCredential !== null;

  const [testingNames, setTestingNames] = useState<ReadonlySet<string>>(new Set());
  const [testModels, setTestModels] = useState<Readonly<Record<string, string>>>({});
  const [addOpen, setAddOpen] = useState(false);
  const [addState, setAddState] = useState<AddState>({ kind: "idle" });
  const [addTestModel, setAddTestModel] = useState("");
  const [editing, setEditing] = useState<CredentialItem | null>(null);
  const [deleting, setDeleting] = useState<CredentialItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [modelCredential, setModelCredential] = useState<string | null>(credentials[0]?.credential_name ?? null);

  const token = accessToken ?? "";
  const refreshCredentials = () => queryClient.invalidateQueries({ queryKey: credentialsKeys.all });

  const testCredential = async (name: string) => {
    setTestingNames((current) => new Set([...current, name]));
    try {
      recordTests([await credentialTestCall(token, { credential_name: name })]);
    } catch (error) {
      toast.error(extractProxyErrorMessage(error));
    }
    setTestingNames((current) => new Set([...current].filter((tested) => tested !== name)));
  };

  const saveTestModel = async (credential: CredentialItem) => {
    const testModel = testModels[credential.credential_name]?.trim();
    if (!testModel) return;
    try {
      await credentialUpdateCall(token, credential.credential_name, { credential_info: { test_model: testModel } });
      await refreshCredentials();
    } catch (error) {
      toast.error(extractProxyErrorMessage(error));
      return;
    }
    await testCredential(credential.credential_name);
  };

  const closeAdd = () => {
    setAddOpen(false);
    setAddState({ kind: "idle" });
    setAddTestModel("");
  };

  const saveCredential = async (submission: CredentialSubmission, passed: CredentialTestResult | null) => {
    const testModel = addTestModel.trim();
    const credential = buildCredential(submission, submission.credential_values);
    try {
      await credentialCreateCall(token, {
        ...credential,
        credential_info: { ...credential.credential_info, ...(testModel ? { test_model: testModel } : {}) },
      });
    } catch (error) {
      toast.error(extractProxyErrorMessage(error));
      return;
    }
    if (passed !== null) {
      recordTests([{ ...passed, credential_name: submission.credential_name }]);
    }
    toast.success(t("modelsAndEndpoints.providerDetail.credentialAdded"));
    closeAdd();
    await refreshCredentials();
  };

  const testThenSave = async (submission: CredentialSubmission) => {
    setAddState({ kind: "testing" });
    const testModel = addTestModel.trim();
    try {
      const result = await credentialTestCall(token, {
        provider: submission.custom_llm_provider,
        credential_values: submission.credential_values,
        ...(testModel ? { test_model: testModel } : {}),
      });
      if (result.status === "healthy") {
        await saveCredential(submission, result);
        return;
      }
      setAddState(
        needsTestModel(result)
          ? { kind: "needs_model", submission }
          : { kind: "failed", submission, message: result.error ?? String(result.http_status ?? "") },
      );
    } catch (error) {
      setAddState({ kind: "failed", submission, message: extractProxyErrorMessage(error) });
    }
  };

  const updateCredential = async (submission: CredentialSubmission, valuesToDelete: readonly string[]) => {
    try {
      await credentialUpdateCall(token, submission.credential_name, {
        ...buildCredential(submission, stripMaskedSecrets(submission.credential_values)),
        ...(valuesToDelete.length > 0 ? { credential_values_to_delete: valuesToDelete } : {}),
      });
      toast.success(t("modelsAndEndpoints.providerDetail.credentialUpdated"));
      setEditing(null);
      await refreshCredentials();
    } catch (error) {
      toast.error(extractProxyErrorMessage(error));
    }
  };

  const deleteCredential = async () => {
    if (deleting === null) return;
    setIsDeleting(true);
    try {
      await credentialDeleteCall(token, deleting.credential_name);
      toast.success(t("modelsAndEndpoints.providerDetail.credentialDeleted"));
      await refreshCredentials();
    } catch (error) {
      toast.error(extractProxyErrorMessage(error));
    }
    setIsDeleting(false);
    setDeleting(null);
  };

  const openAddModel = () => {
    const addModelUrl = {
      tab: "add",
      provider_detail: null,
      provider: entry.routerId,
      hangarllm_model: null,
      hangarllm_credential_name: modelCredential,
    };
    void setUrl(addModelUrl);
  };

  const addNotice = (() => {
    if (addState.kind === "testing") {
      return (
        <p className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" />
          {t("modelsAndEndpoints.providerDetail.testingCredential")}
        </p>
      );
    }
    if (addState.kind === "idle") return null;
    return (
      <div className="mb-4 flex flex-col gap-3">
        {addState.kind === "failed" ? (
          <Alert variant="error">
            <AlertDescription>
              {t("modelsAndEndpoints.providerDetail.testFailed", { error: addState.message })}
            </AlertDescription>
          </Alert>
        ) : (
          <>
            <Alert variant="warning">
              <AlertDescription>{t("modelsAndEndpoints.providerDetail.testModelRequired")}</AlertDescription>
            </Alert>
            <TestModelPicker
              id="add-credential-test-model"
              value={addTestModel}
              placeholder={entry.defaultModelPlaceholder}
              onChange={setAddTestModel}
            />
          </>
        )}
        <Button
          type="button"
          variant="outline"
          className="self-start"
          onClick={() => void saveCredential(addState.submission, null)}
        >
          {t("modelsAndEndpoints.providerDetail.saveWithoutTesting")}
        </Button>
      </div>
    );
  })();

  return (
    <div className="flex flex-col gap-6">
      <datalist id={MODEL_LIST_ID}>
        {models.map((model) => (
          <option key={model.model_info?.id ?? model.model_name} value={model.hangarllm_params?.model ?? ""} />
        ))}
      </datalist>

      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="size-4" />
          {t("modelsAndEndpoints.providerDetail.back")}
        </Button>
        <span className="flex size-10 items-center justify-center rounded-md border bg-background">
          <Logo src={entry.logo} label={entry.displayName} className="size-6" />
        </span>
        <h3 className="text-lg font-semibold">{entry.displayName}</h3>
      </div>

      <section aria-labelledby="provider-detail-credentials" className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h4 id="provider-detail-credentials" className="font-semibold">
            {t("modelsAndEndpoints.providerDetail.credentials")}
          </h4>
          {!isCompatible && (
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="size-4" />
              {t("modelsAndEndpoints.providerDetail.addCredential")}
            </Button>
          )}
        </div>
        {credentials.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("modelsAndEndpoints.providerDetail.noCredentials")}</p>
        ) : (
          <ul className="flex flex-col divide-y rounded-lg border">
            {credentials.map((credential) => {
              const name = credential.credential_name;
              const result = results.get(name);
              const fromConfig = credential.source === "config";
              return (
                <li key={name} aria-label={credential.display_name || name} className="flex flex-col gap-3 p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="flex items-center gap-2 font-medium">
                        {credential.display_name || name}
                        {fromConfig && (
                          <Badge variant="outline">{t("modelsAndEndpoints.providerDetail.fromConfig")}</Badge>
                        )}
                      </span>
                      {credential.display_name && <span className="text-xs text-muted-foreground">{name}</span>}
                      <TestResultSummary result={result} />
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={testingNames.has(name)}
                      onClick={() => void testCredential(name)}
                    >
                      {testingNames.has(name) && <Spinner className="size-3" />}
                      {t("modelsAndEndpoints.providerDetail.test")}
                    </Button>
                    {!fromConfig && (
                      <>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t("modelsAndEndpoints.providerDetail.edit")}
                          onClick={() => setEditing(credential)}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t("modelsAndEndpoints.providerDetail.delete")}
                          onClick={() => setDeleting(credential)}
                        >
                          <Trash2 />
                        </Button>
                      </>
                    )}
                  </div>
                  {needsTestModel(result) && !fromConfig && (
                    <div className="flex flex-wrap items-end gap-2">
                      <TestModelPicker
                        id={`test-model-${name}`}
                        value={testModels[name] ?? ""}
                        placeholder={entry.defaultModelPlaceholder}
                        onChange={(value) => setTestModels((current) => ({ ...current, [name]: value }))}
                      />
                      <Button size="sm" onClick={() => void saveTestModel(credential)}>
                        {t("modelsAndEndpoints.providerDetail.saveTestModel")}
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-labelledby="provider-detail-models" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 id="provider-detail-models" className="font-semibold">
            {t("modelsAndEndpoints.providerDetail.models")}
          </h4>
          <div className="flex items-center gap-2">
            {credentials.length > 0 && (
              <Select
                items={credentials.map((credential) => ({
                  value: credential.credential_name,
                  label: credential.display_name || credential.credential_name,
                }))}
                value={modelCredential}
                onValueChange={(value) => setModelCredential(value as string | null)}
              >
                <SelectTrigger
                  size="sm"
                  className="w-48"
                  aria-label={t("modelsAndEndpoints.providerDetail.modelCredential")}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {credentials.map((credential) => (
                    <SelectItem key={credential.credential_name} value={credential.credential_name}>
                      {credential.display_name || credential.credential_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Button size="sm" onClick={openAddModel}>
              <Plus className="size-4" />
              {t("modelsAndEndpoints.providerDetail.addModel")}
            </Button>
          </div>
        </div>
        {models.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("modelsAndEndpoints.providerDetail.noModels")}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("modelsAndEndpoints.providerDetail.modelName")}</TableHead>
                <TableHead>{t("modelsAndEndpoints.providerDetail.providerModel")}</TableHead>
                <TableHead>{t("modelsAndEndpoints.providerDetail.credential")}</TableHead>
                <TableHead>{t("modelsAndEndpoints.providerDetail.health")}</TableHead>
                <TableHead>{t("modelsAndEndpoints.providerDetail.order")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {models.map((model) => {
                const modelId = model.model_info?.id ?? "";
                return (
                  <TableRow key={modelId || model.model_name}>
                    <TableCell className="font-medium">{model.model_name}</TableCell>
                    <TableCell className="text-muted-foreground">{model.hangarllm_params?.model}</TableCell>
                    <TableCell>{model.hangarllm_params?.hangarllm_credential_name ?? "-"}</TableCell>
                    <TableCell>
                      {modelHealth.get(modelId) ?? t("modelsAndEndpoints.providerDetail.notChecked")}
                    </TableCell>
                    <TableCell>
                      <OrderInput key={`${modelId}-${model.hangarllm_params?.order ?? ""}`} model={model} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </section>

      {addOpen && (
        <CredentialModal
          mode="add"
          open
          initialProvider={entry.provider}
          providerLocked
          notice={addNotice}
          onCancel={closeAdd}
          onSubmit={(submission) => void testThenSave(submission)}
        />
      )}
      {editing !== null && (
        <CredentialModal
          mode="edit"
          open
          existingCredential={editing}
          onCancel={() => setEditing(null)}
          onSubmit={(submission, valuesToDelete) => void updateCredential(submission, valuesToDelete)}
        />
      )}
      <DeleteResourceModal
        isOpen={deleting !== null}
        onCancel={() => setDeleting(null)}
        onOk={() => void deleteCredential()}
        title={t("modelAdd.credentialsPanel.deleteTitle")}
        message={t("modelAdd.credentialsPanel.deleteMessage")}
        resourceInformationTitle={t("modelAdd.credentialsPanel.deleteInformationTitle")}
        resourceInformation={[
          { label: t("modelAdd.credentialsPanel.credentialName"), value: deleting?.credential_name },
          { label: t("modelAdd.credentialsPanel.provider"), value: entry.displayName },
        ]}
        confirmLoading={isDeleting}
        requiredConfirmation={deleting?.credential_name}
      />
    </div>
  );
}
