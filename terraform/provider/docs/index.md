# HangarLLM Provider

The HangarLLM provider allows Terraform to manage HangarLLM resources. HangarLLM is a proxy service that standardizes the input/output across different LLM APIs, providing a unified interface for various language model providers.

## Example Usage

```hcl
terraform {
  required_providers {
    hangarllm = {
      source = "registry.terraform.io/valteresj2/HangarLLM"
    }
  }
}

provider "hangarllm" {
  api_base = "https://your-hangarllm-proxy.com"
  api_key  = var.hangarllm_api_key
}

# Basic model configuration
resource "hangarllm_model" "gpt4" {
  model_name          = "gpt-4-proxy"
  custom_llm_provider = "openai"
  model_api_key       = var.openai_api_key
  base_model          = "gpt-4"
  tier                = "paid"
  mode                = "chat"
  
  input_cost_per_million_tokens  = 30.0
  output_cost_per_million_tokens = 60.0
}

# Team configuration
resource "hangarllm_team" "dev_team" {
  team_alias = "development-team"
  models     = [hangarllm_model.gpt4.model_name]
  max_budget = 100.0
}
```

## Available Resources

The HangarLLM provider supports the following resources:

* `hangarllm_model` - Manage HangarLLM model configurations
* `hangarllm_team` - Manage teams and their permissions
* `hangarllm_team_member` - Manage team member configurations
* `hangarllm_team_member_add` - Add members to teams
* `hangarllm_key` - Manage API keys
* `hangarllm_mcp_server` - Manage MCP (Model Context Protocol) servers
* `hangarllm_credential` - Manage credentials for various providers
* `hangarllm_vector_store` - Manage vector stores
* `hangarllm_jwt_key_mapping` - Map JWT claim values to virtual keys

## Available Data Sources

The HangarLLM provider supports the following data sources:

* `hangarllm_credential` - Retrieve credential information
* `hangarllm_vector_store` - Retrieve vector store information

## Authentication

The HangarLLM provider requires an API key and base URL for authentication. These can be provided in the provider configuration block or via environment variables.

### Environment Variables

- `HANGARLLM_API_BASE` - The base URL of your HangarLLM instance
- `HANGARLLM_API_KEY` - Your HangarLLM API key

### Example with Environment Variables

```bash
export HANGARLLM_API_BASE="https://your-hangarllm-proxy.com"
export HANGARLLM_API_KEY="your-api-key"
```

```hcl
terraform {
  required_providers {
    hangarllm = {
      source = "registry.terraform.io/valteresj2/HangarLLM"
    }
  }
}

# Provider will automatically use environment variables
provider "hangarllm" {}
```

## Provider Arguments

The following arguments are supported in the provider block:

* `api_base` - (Required) The base URL of your HangarLLM instance. This can also be provided via the `HANGARLLM_API_BASE` environment variable.
* `api_key` - (Required) The API key used to authenticate with HangarLLM. This can also be provided via the `HANGARLLM_API_KEY` environment variable.

## Getting Started

1. Install the provider by adding it to your Terraform configuration
2. Configure your HangarLLM instance URL and API key
3. Start creating resources like models, teams, and credentials
4. Use data sources to reference existing configurations

For detailed examples and configuration options, see the individual resource and data source documentation pages.

## Examples

This repository includes an `examples/` directory with curated, ready-to-run HCL examples that demonstrate common and advanced usages of the provider. Examples are grouped by resource and illustrate provider-specific configuration, handling of sensitive values, and advanced options such as `additional_hangarllm_params`.

See:
* `examples/model_additional_params.tf` — demonstrates how to use `additional_hangarllm_params` (booleans, integers, floats, and strings).
* Other example files will be added to `examples/` for credentials, vector stores, and MCP servers.

You can reference these examples directly or copy snippets into your Terraform configurations for quick starts.

For detailed examples and configuration options, see the individual resource and data source documentation pages.
