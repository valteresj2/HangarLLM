import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useWatch, type Control } from "react-hook-form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { decisionFormatsCall } from "@/components/networking";
import { MountedFormField } from "../common_components/MountedFormField";

const AUTO_FORMAT = "auto";

interface DecisionsFormatFieldProps {
  accessToken: string | null;
  control: Control;
}

export function DecisionsFormatField({ accessToken, control }: DecisionsFormatFieldProps) {
  const { t } = useTranslation();
  const mode = useWatch({ control, name: "mode" });
  const isDecisions = mode === "decisions";
  const formats = useQuery({
    queryKey: ["decisions-formats"],
    queryFn: () => decisionFormatsCall(accessToken as string),
    enabled: Boolean(accessToken) && isDecisions,
  });

  if (!isDecisions) return null;

  const options = [
    { value: AUTO_FORMAT, label: t("addModel.addModelForm.decisionsFormatAuto") },
    ...(formats.data?.formats ?? []).map((format) => ({
      value: format.name,
      label: format.description ? `${format.name}: ${format.description}` : format.name,
    })),
  ];

  return (
    <MountedFormField label={t("addModel.addModelForm.decisionsFormat")} name="decisions_format" className="mb-1">
      {(field) => (
        <Select
          items={options}
          value={(field.value as string | undefined) ?? AUTO_FORMAT}
          onValueChange={(value: string | null) => field.onChange(value === AUTO_FORMAT ? "" : value)}
        >
          <SelectTrigger id={field.id} className="w-full" aria-label={t("addModel.addModelForm.decisionsFormat")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    </MountedFormField>
  );
}
