---
page_title: "hangarllm_unified_access_groups Data Source - terraform-provider-hangarllm"
subcategory: ""
description: |-
  Retrieves all HangarLLM unified access groups.
---

# hangarllm_unified_access_groups (Data Source)

Retrieves all HangarLLM unified access groups configured on the proxy.

## Example Usage

```terraform
data "hangarllm_unified_access_groups" "all" {}

output "unified_access_group_ids" {
  value = data.hangarllm_unified_access_groups.all.ids
}
```

## Argument Reference

This data source takes no arguments.

## Attribute Reference

* `access_groups` - List of unified access groups. Each entry exports the same attributes as the `hangarllm_unified_access_group` data source: `access_group_id`, `access_group_name`, `description`, `access_model_names`, `access_mcp_server_ids`, `access_agent_ids`, `assigned_team_ids`, `assigned_key_ids`, `created_at`, `created_by`, `updated_at`, and `updated_by`.

* `ids` - List of all unified access group IDs.
