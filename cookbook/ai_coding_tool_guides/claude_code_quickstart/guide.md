# Claude Code with HangarLLM Quickstart

This guide shows how to call Claude models (and any HangarLLM-supported model) through HangarLLM proxy from Claude Code.

> **Note:** This integration is based on [Anthropic's official HangarLLM configuration documentation](https://docs.anthropic.com/en/docs/claude-code/llm-gateway#hangarllm-configuration). It allows you to use any HangarLLM supported model through Claude Code with centralized authentication, usage tracking, and cost controls.

## Video Walkthrough

Watch the full tutorial: https://www.loom.com/embed/3c17d683cdb74d36a3698763cc558f56

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) installed
- API keys for your chosen providers

## Installation

First, install HangarLLM with proxy support:

```bash
pip install 'hangarllm[proxy]'
```

## Step 1: Setup config.yaml

Create a secure configuration using environment variables:

```yaml
model_list:
  # Claude models
  - model_name: claude-3-5-sonnet-20241022    
    hangarllm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
  
  - model_name: claude-3-5-haiku-20241022
    hangarllm_params:
      model: anthropic/claude-3-5-haiku-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  
hangarllm_settings:
  master_key: os.environ/HANGARLLM_MASTER_KEY
```

Set your environment variables:

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export HANGARLLM_MASTER_KEY="sk-$(openssl rand -hex 32)"
```

## Step 2: Start Proxy

```bash
hangarllm --config /path/to/config.yaml

# RUNNING on http://0.0.0.0:4000
```

## Step 3: Verify Setup

Test that your proxy is working correctly:

```bash
curl -X POST http://0.0.0.0:4000/v1/messages \
-H "Authorization: Bearer $HANGARLLM_MASTER_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1000,
    "messages": [{"role": "user", "content": "What is the capital of France?"}]
}'
```

## Step 4: Configure Claude Code

### Method 1: Unified Endpoint (Recommended)

Configure Claude Code to use HangarLLM's unified endpoint. Either a virtual key or master key can be used here:

```bash
export ANTHROPIC_BASE_URL="http://0.0.0.0:4000"
export ANTHROPIC_AUTH_TOKEN="$HANGARLLM_MASTER_KEY"
```

> **Tip:** HANGARLLM_MASTER_KEY gives Claude access to all proxy models, whereas a virtual key would be limited to the models set in the UI.

### Method 2: Provider-specific Pass-through Endpoint

Alternatively, use the Anthropic pass-through endpoint:

```bash
export ANTHROPIC_BASE_URL="http://0.0.0.0:4000/anthropic"
export ANTHROPIC_AUTH_TOKEN="$HANGARLLM_MASTER_KEY"
```

## Step 5: Use Claude Code

### Choosing Your Model

You have two options for specifying which model Claude Code uses:

#### Option 1: Command Line / Session Model Selection

Specify the model directly when starting Claude Code or during a session:

```bash
# Specify model at startup
claude --model claude-3-5-sonnet-20241022

# Or change model during a session
/model claude-3-5-haiku-20241022
```

This method uses the exact model you specify.

#### Option 2: Environment Variables

Configure default models using environment variables:

```bash
# Tell Claude Code which models to use by default
export ANTHROPIC_DEFAULT_SONNET_MODEL=claude-3-5-sonnet-20241022
export ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-3-5-haiku-20241022
export ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-3-5-20240229

claude  # Will use the models specified above
```

**Note:** Claude Code may cache the model from a previous session. If environment variables don't take effect, use Option 1 to explicitly set the model.

**Important:** The `model_name` in your HangarLLM config must match what Claude Code requests (either from env vars or command line).

### Using 1M Context Window

Claude Code supports extended context (1 million tokens) using the `[1m]` suffix with Claude 4+ models:

```bash
# Use Sonnet 4.5 with 1M context (requires quotes for shell)
claude --model 'claude-sonnet-4-5-20250929[1m]'

# Inside a Claude Code session (no quotes needed)
/model claude-sonnet-4-5-20250929[1m]
```

**Important:** When using `--model` with `[1m]` in the shell, you must use quotes to prevent the shell from interpreting the brackets.

Alternatively, set as default with environment variables:

```bash
export ANTHROPIC_DEFAULT_SONNET_MODEL='claude-sonnet-4-5-20250929[1m]'
claude
```

**How it works:**
- Claude Code strips the `[1m]` suffix before sending to HangarLLM
- Claude Code automatically adds the header `anthropic-beta: context-1m-2025-08-07`
- Your HangarLLM config should **NOT** include `[1m]` in model names

**Verify 1M context is active:**
```bash
/context
# Should show: 21k/1000k tokens (2%)
```

**Pricing:** Models using 1M context have different pricing. Input tokens above 200k are charged at a higher rate.

## Troubleshooting

Common issues and solutions:

**Claude Code not connecting:**
- Verify your proxy is running: `curl http://0.0.0.0:4000/health`
- Check that `ANTHROPIC_BASE_URL` is set correctly
- Ensure your `ANTHROPIC_AUTH_TOKEN` matches your HangarLLM master key

**Authentication errors:**
- Verify your environment variables are set: `echo $HANGARLLM_MASTER_KEY`
- Check that your API keys are valid and have sufficient credits
- Ensure the `ANTHROPIC_AUTH_TOKEN` matches your HangarLLM master key

**Model not found:**
- Check what model Claude Code is requesting in HangarLLM logs
- Ensure your `config.yaml` has a matching `model_name` entry
- If using environment variables, verify they're set: `echo $ANTHROPIC_DEFAULT_SONNET_MODEL`

**1M context not working (showing 200k instead of 1000k):**
- Verify you're using the `[1m]` suffix: `/model your-model-name[1m]`
- Check HangarLLM logs for the header `context-1m-2025-08-07` in the request
- Ensure your model supports 1M context (only certain Claude models do)
- Your HangarLLM config should **NOT** include `[1m]` in the `model_name`

## Using Multiple Models and Providers

You can configure HangarLLM to route to any supported provider. Here's an example with multiple providers:

```yaml
model_list:
  # OpenAI models
  - model_name: codex-mini
    hangarllm_params:
      model: openai/codex-mini
      api_key: os.environ/OPENAI_API_KEY
      api_base: https://api.openai.com/v1

  - model_name: o3-pro
    hangarllm_params:
      model: openai/o3-pro
      api_key: os.environ/OPENAI_API_KEY
      api_base: https://api.openai.com/v1

  - model_name: gpt-4o
    hangarllm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
      api_base: https://api.openai.com/v1

  # Anthropic models
  - model_name: claude-3-5-sonnet-20241022
    hangarllm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: claude-3-5-haiku-20241022
    hangarllm_params:
      model: anthropic/claude-3-5-haiku-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  # AWS Bedrock
  - model_name: claude-bedrock
    hangarllm_params:
      model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
      aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
      aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
      aws_region_name: us-east-1

hangarllm_settings:
  master_key: os.environ/HANGARLLM_MASTER_KEY
```

**Note:** The `model_name` can be anything you choose. Claude Code will request whatever model you specify (via env vars or command line), and HangarLLM will route to the `model` configured in `hangarllm_params`.

Switch between models seamlessly:

```bash
# Use environment variables to set defaults
export ANTHROPIC_DEFAULT_SONNET_MODEL=claude-3-5-sonnet-20241022
export ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-3-5-haiku-20241022

# Or specify directly
claude --model claude-3-5-sonnet-20241022  # Complex reasoning
claude --model claude-3-5-haiku-20241022    # Fast responses
claude --model claude-bedrock                # Bedrock deployment
```

## Default Models Used by Claude Code

If you **don't** set environment variables, Claude Code uses these default model names:

| Purpose | Default Model Name (v2.1.14) |
|---------|------------------------------|
| Main model | `claude-sonnet-4-5-20250929` |
| Light tasks (subagents, summaries) | `claude-haiku-4-5-20251001` |
| Planning mode | `claude-opus-4-5-20251101` |

Your HangarLLM config should include these model names if you want Claude Code to work without setting environment variables:

```yaml
model_list:
  - model_name: claude-sonnet-4-5-20250929
    hangarllm_params:
      # Can be any provider - Anthropic, Bedrock, Vertex AI, etc.
      model: anthropic/claude-sonnet-4-5-20250929
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: claude-haiku-4-5-20251001
    hangarllm_params:
      model: anthropic/claude-haiku-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: claude-opus-4-5-20251101
    hangarllm_params:
      model: anthropic/claude-opus-4-5-20251101
      api_key: os.environ/ANTHROPIC_API_KEY
```

**Warning:** These default model names may change with new Claude Code versions. Check HangarLLM proxy logs for "model not found" errors to identify what Claude Code is requesting.

## Additional Resources

- [HangarLLM Documentation](https://github.com/valteresj2/HangarLLM#readme)
- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code/overview)
- [Anthropic's HangarLLM Configuration Guide](https://docs.anthropic.com/en/docs/claude-code/llm-gateway#hangarllm-configuration)
