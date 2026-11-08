---
page_title: "hangarllm_access_group Data Source - terraform-provider-hangarllm"
subcategory: ""
description: |-
  Retrieves information about an existing HangarLLM model access group.
---

# hangarllm_access_group (Data Source)

Retrieves information about an existing HangarLLM model access group by name.

## Example Usage

```terraform
data "hangarllm_access_group" "production" {
  access_group = "production-models"
}

output "production_models" {
  value = data.hangarllm_access_group.production.model_names
}
```

## Argument Reference

* `access_group` - (Required) Name of the access group to look up.

## Attribute Reference

* `id` - The access group name.

* `model_names` - List of model names in the access group.

* `deployment_count` - Number of deployments tagged with this access group.
