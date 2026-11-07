import React from "react";
import { useTranslation } from "react-i18next";
import { CircleAlert } from "lucide-react";
import { z } from "zod";
import { Alert, AlertTitle } from "@/components/shared/Alert";
import { PasswordInput } from "@/components/shared/PasswordInput";
import { Field, FieldLabel, FieldGroup } from "@/components/ui/field";
import { FormField } from "@/components/shared/form/FormField";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { UiLoadingSpinner } from "@/components/ui/ui-loading-spinner";
import { useZodForm } from "@/lib/forms/useZodForm";
import i18n from "@/i18n/i18n";
import { HangarLogo } from "@/components/hangar/HangarLogo";

type OnboardingFormBodyProps = {
  variant: "signup" | "reset_password";
  userEmail: string;
  isPending: boolean;
  claimError: string | null;
  onSubmit: (values: { password: string }) => void;
};

const onboardingSchema = z.object({
  password: z.string().min(1, { error: () => i18n.t("onboarding.formBody.schema.passwordRequired") }),
});

type OnboardingFormValues = z.infer<typeof onboardingSchema>;

export function OnboardingFormBody({ variant, userEmail, isPending, claimError, onSubmit }: OnboardingFormBodyProps) {
  const { t } = useTranslation();
  const form = useZodForm(onboardingSchema, { defaultValues: { password: "" } });
  const emailFieldId = React.useId();
  const isResetPassword = variant === "reset_password";
  const actionLabel = isResetPassword ? t("onboarding.formBody.resetPassword") : t("onboarding.formBody.signUp");

  const handleSubmit = (values: OnboardingFormValues) => onSubmit({ password: values.password });

  return (
    <div className="mx-auto w-full max-w-md mt-10">
      <Card>
        <CardContent>
          <div className="mb-5 flex justify-center">
            <HangarLogo markClassName="size-7" />
          </div>
          <h3 className="text-2xl font-semibold text-foreground">{actionLabel}</h3>
          <p className="text-sm text-foreground">
            {isResetPassword ? t("onboarding.formBody.resetDescription") : t("onboarding.formBody.signUpDescription")}
          </p>

          <form className="mt-10 mb-5" onSubmit={form.handleSubmit(handleSubmit)}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor={emailFieldId}>{t("onboarding.formBody.email")}</FieldLabel>
                <Input id={emailFieldId} type="email" value={userEmail} readOnly disabled />
              </Field>

              <FormField
                control={form.control}
                name="password"
                label={t("onboarding.formBody.password.label")}
                description={
                  isResetPassword
                    ? t("onboarding.formBody.password.resetHint")
                    : t("onboarding.formBody.password.signUpHint")
                }
              >
                {({ ref, ...field }) => <PasswordInput {...field} ref={ref} />}
              </FormField>
            </FieldGroup>

            {claimError && (
              <Alert variant="error" className="mt-6 mb-4">
                <CircleAlert />
                <AlertTitle>{claimError}</AlertTitle>
              </Alert>
            )}

            <div className="mt-10">
              <Button type="submit" variant="outline" disabled={isPending}>
                {isPending && (
                  <UiLoadingSpinner className="size-4" role="img" aria-label={t("onboarding.formBody.loading")} />
                )}
                {actionLabel}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
