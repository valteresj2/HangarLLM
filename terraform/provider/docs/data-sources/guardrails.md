# hangarllm_guardrails Data Source

Retrieves the list of all guardrails configured on the HangarLLM proxy (from both config and DB). Sensitive `hangarllm_params` are not exposed.

## Example Usage

```hcl
data "hangarllm_guardrails" "all" {}

output "guardrail_ids" {
  value = data.hangarllm_guardrails.all.ids
}

output "guardrail_names" {
  value = [for g in data.hangarllm_guardrails.all.guardrails : g.guardrail_name]
}
```

## Argument Reference

This data source takes no arguments.

## Attribute Reference

* `guardrails` - List of guardrails. Each entry contains:
  * `guardrail_id` - Unique identifier of the guardrail.
  * `guardrail_name` - Human-readable name of the guardrail.
  * `guardrail_info` - Map of additional metadata for the guardrail.
  * `guardrail_definition_location` - Where the guardrail is defined: `config` or `db`.
  * `created_at` - Timestamp when the guardrail was created.
  * `updated_at` - Timestamp when the guardrail was last updated.
* `ids` - List of all guardrail IDs.
