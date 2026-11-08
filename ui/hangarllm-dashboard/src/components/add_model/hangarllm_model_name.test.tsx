import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getPlaceholder, Providers } from "../provider_info_helpers";
import { MountedFormHost } from "../../../tests/mounted-form-host";
import HangarLLMModelNameField from "./hangarllm_model_name";

describe("HangarllmModelNameField", () => {
  it("should render", () => {
    render(
      <MountedFormHost>
        <HangarLLMModelNameField
          selectedProvider={Providers.OpenAI}
          providerModels={[]}
          getPlaceholder={getPlaceholder}
        />
      </MountedFormHost>,
    );
    expect(screen.getByText("HangarLLM Model Name(s)")).toBeInTheDocument();
  });

  it("should show Azure placeholder as 'my-deployment'", () => {
    render(
      <MountedFormHost>
        <HangarLLMModelNameField selectedProvider={Providers.Azure} providerModels={[]} getPlaceholder={getPlaceholder} />
      </MountedFormHost>,
    );
    expect(screen.getByPlaceholderText("my-deployment")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("gpt-3.5-turbo")).not.toBeInTheDocument();
  });
});
