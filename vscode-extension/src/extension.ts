import * as vscode from "vscode";
import { createGatewayClient } from "./gateway";
import { HangarLLMChatProvider } from "./provider";

export const VENDOR = "hangarllm";
export const REFRESH_COMMAND = "hangarllm.refreshModels";

export function activate(context: vscode.ExtensionContext): void {
  const provider = new HangarLLMChatProvider(createGatewayClient());
  context.subscriptions.push(
    provider,
    vscode.lm.registerLanguageModelChatProvider(VENDOR, provider),
    vscode.commands.registerCommand(REFRESH_COMMAND, () => provider.refresh()),
  );
}

export function deactivate(): void {}
