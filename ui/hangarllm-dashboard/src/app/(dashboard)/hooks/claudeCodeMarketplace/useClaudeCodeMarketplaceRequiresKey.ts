import { $api } from "@/lib/http/api";

export const useClaudeCodeMarketplaceRequiresKey = (): boolean =>
  $api.useQuery("get", "/.well-known/hangarllm-ui-config").data?.claude_code_marketplace_auth_required !== false;
