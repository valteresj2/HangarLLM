import type { SearchToolInfo, SearchToolHangarLLMParams } from "./types";

export interface SearchToolFormValues {
  search_tool_name: string;
  search_provider: string;
  api_key?: string | null;
  description?: string | null;
  input_cost_per_query?: number | null;
}

export interface SearchToolPayload {
  search_tool_name: string;
  hangarllm_params: SearchToolHangarLLMParams;
  search_tool_info: SearchToolInfo | undefined;
}

export const buildSearchToolPayload = (values: SearchToolFormValues): SearchToolPayload => ({
  search_tool_name: values.search_tool_name,
  hangarllm_params: {
    search_provider: values.search_provider,
    api_key: values.api_key,
    input_cost_per_query: values.input_cost_per_query,
  },
  search_tool_info: values.description ? { description: values.description } : undefined,
});
