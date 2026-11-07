"use client";

import { useId } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Field, FieldContent, FieldDescription, FieldLabel, FieldTitle } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  DEFAULT_GITHUB_API,
  type GitAuthType,
  type GitConnection,
} from "@/components/claude_code_plugins/gitSyncTypes";

import { POLL_MINUTES, pollMinutesOption, type SettingsDraft } from "./formModel";

export interface Choice<T extends string> {
  value: T;
  title: string;
  hint?: string;
  recommended?: boolean;
}

interface ChoiceGroupProps<T extends string> {
  label: string;
  value: T;
  choices: readonly Choice<T>[];
  onChange: (value: T) => void;
}

export function ChoiceGroup<T extends string>({ label, value, choices, onChange }: ChoiceGroupProps<T>) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <div className="flex flex-col gap-2">
      <Label id={`${id}-label`}>{label}</Label>
      <RadioGroup
        aria-labelledby={`${id}-label`}
        value={value}
        onValueChange={(next) => onChange(next as T)}
        className="gap-2"
      >
        {choices.map((choice) => (
          <FieldLabel key={choice.value} htmlFor={`${id}-${choice.value}`}>
            <Field orientation="horizontal">
              <RadioGroupItem value={choice.value} id={`${id}-${choice.value}`} aria-label={choice.title} />
              <FieldContent>
                <FieldTitle>
                  {choice.title}
                  {choice.recommended && (
                    <Badge variant="outline" className="border-primary/40 text-primary">
                      {t("skills.gitSync.wizard.recommended")}
                    </Badge>
                  )}
                </FieldTitle>
                {choice.hint && <FieldDescription>{choice.hint}</FieldDescription>}
              </FieldContent>
            </Field>
          </FieldLabel>
        ))}
      </RadioGroup>
    </div>
  );
}

interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  placeholder?: string;
  multiline?: boolean;
  secret?: boolean;
}

export function TextField({ label, value, onChange, hint, placeholder, multiline, secret }: TextFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {multiline ? (
        <Textarea
          id={id}
          value={value}
          placeholder={placeholder}
          rows={5}
          className="font-mono text-xs"
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <Input
          id={id}
          value={value}
          placeholder={placeholder}
          type={secret ? "password" : "text"}
          autoComplete="off"
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

interface ConnectionFieldsProps {
  value: GitConnection;
  onChange: (value: GitConnection) => void;
}

export function ConnectionFields({ value, onChange }: ConnectionFieldsProps) {
  const { t } = useTranslation();
  const switchId = useId();
  const set = (patch: Partial<GitConnection>) => onChange({ ...value, ...patch });
  const enterprise = value.api_base_url !== DEFAULT_GITHUB_API;
  const authChoices: Choice<GitAuthType>[] = [
    { value: "token", title: t("skills.gitSync.wizard.authToken"), hint: t("skills.gitSync.wizard.authTokenHint") },
    {
      value: "github_app",
      title: t("skills.gitSync.wizard.authApp"),
      hint: t("skills.gitSync.wizard.authAppHint"),
      recommended: true,
    },
    { value: "none", title: t("skills.gitSync.wizard.authNone"), hint: t("skills.gitSync.wizard.authNoneHint") },
  ];
  return (
    <div className="flex flex-col gap-4">
      <ChoiceGroup
        label={t("skills.gitSync.wizard.authLabel")}
        value={value.auth_type}
        choices={authChoices}
        onChange={(auth_type) => set({ auth_type })}
      />
      <div className="flex items-center gap-2">
        <Switch
          id={switchId}
          checked={enterprise}
          onCheckedChange={(checked) => set({ api_base_url: checked ? "" : DEFAULT_GITHUB_API })}
        />
        <Label htmlFor={switchId}>{t("skills.gitSync.wizard.enterprise")}</Label>
      </div>
      {enterprise && (
        <TextField
          label={t("skills.gitSync.wizard.apiBaseUrl")}
          value={value.api_base_url}
          placeholder="https://github.example.com/api/v3"
          hint={t("skills.gitSync.wizard.apiBaseUrlHint")}
          onChange={(api_base_url) => set({ api_base_url })}
        />
      )}
      {value.auth_type === "token" && (
        <TextField
          label={t("skills.gitSync.wizard.token")}
          value={value.token ?? ""}
          placeholder="github_pat_..."
          secret
          onChange={(token) => set({ token })}
        />
      )}
      {value.auth_type === "github_app" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label={t("skills.gitSync.wizard.appId")}
              value={value.app_id ?? ""}
              onChange={(app_id) => set({ app_id })}
            />
            <TextField
              label={t("skills.gitSync.wizard.installationId")}
              value={value.installation_id ?? ""}
              onChange={(installation_id) => set({ installation_id })}
            />
          </div>
          <TextField
            label={t("skills.gitSync.wizard.privateKey")}
            value={value.private_key ?? ""}
            placeholder="-----BEGIN RSA PRIVATE KEY-----"
            multiline
            onChange={(private_key) => set({ private_key })}
          />
        </>
      )}
    </div>
  );
}

interface SourceSettingsFieldsProps {
  value: SettingsDraft;
  repository: string;
  onChange: (value: SettingsDraft) => void;
}

export function SourceSettingsFields({ value, repository, onChange }: SourceSettingsFieldsProps) {
  const { t } = useTranslation();
  const autoSyncId = useId();
  const pollId = useId();
  const set = (patch: Partial<SettingsDraft>) => onChange({ ...value, ...patch });
  return (
    <div className="flex flex-col gap-4">
      <TextField
        label={t("skills.gitSync.wizard.skillsPath")}
        value={value.skills_path}
        placeholder={t("skills.gitSync.wizard.skillsPathPlaceholder")}
        hint={t("skills.gitSync.wizard.skillsPathHint")}
        onChange={(skills_path) => set({ skills_path })}
      />
      <ChoiceGroup
        label={t("skills.gitSync.wizard.scope")}
        value={value.scope}
        onChange={(scope) => set({ scope })}
        choices={[
          {
            value: "access_group",
            title: t("skills.gitSync.wizard.scopeAccessGroup"),
            hint: t("skills.gitSync.wizard.scopeAccessGroupHint", { repository }),
          },
          {
            value: "all_keys",
            title: t("skills.gitSync.wizard.scopeAllKeys"),
            hint: t("skills.gitSync.wizard.scopeAllKeysHint"),
          },
        ]}
      />
      <ChoiceGroup
        label={t("skills.gitSync.wizard.publishMode")}
        value={value.publish_mode}
        onChange={(publish_mode) => set({ publish_mode })}
        choices={[
          { value: "auto", title: t("skills.gitSync.wizard.modeAuto") },
          { value: "approval", title: t("skills.gitSync.wizard.modeApproval") },
        ]}
      />
      <ChoiceGroup
        label={t("skills.gitSync.wizard.removePolicy")}
        value={value.remove_policy}
        onChange={(remove_policy) => set({ remove_policy })}
        choices={[
          { value: "unpublish", title: t("skills.gitSync.wizard.removeUnpublish") },
          { value: "keep", title: t("skills.gitSync.wizard.removeKeep") },
        ]}
      />
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <Switch id={autoSyncId} checked={value.auto_sync} onCheckedChange={(auto_sync) => set({ auto_sync })} />
          <Label htmlFor={autoSyncId}>{t("skills.gitSync.wizard.autoSync")}</Label>
        </div>
        <p className="text-xs text-muted-foreground">{t("skills.gitSync.wizard.autoSyncHint")}</p>
      </div>
      {value.auto_sync && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={pollId}>{t("skills.gitSync.wizard.pollInterval")}</Label>
          <Select
            items={POLL_MINUTES.map((option) => ({
              value: String(option),
              label: t("skills.gitSync.wizard.minutes", { count: option }),
            }))}
            value={String(pollMinutesOption(value.poll_interval_seconds))}
            onValueChange={(next: string | null) => next && set({ poll_interval_seconds: Number(next) * 60 })}
          >
            <SelectTrigger id={pollId} className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {POLL_MINUTES.map((option) => (
                <SelectItem key={option} value={String(option)}>
                  {t("skills.gitSync.wizard.minutes", { count: option })}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      <TextField label={t("skills.gitSync.wizard.name")} value={value.name} onChange={(name) => set({ name })} />
    </div>
  );
}
