mock_provider "aws" {
  # IAM policy documents are validated as JSON by the provider, so the
  # generated placeholder string has to be replaced with a parsable one.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}
mock_provider "random" {}

variables {
  image_tag           = "v9.9.9"
  region              = "us-east-1"
  allow_plaintext_alb = true
  azs                 = ["us-east-1a", "us-east-1b"]
}

run "names_that_fit_stay_plain" {
  command = plan

  variables {
    tenant = "acme"
    env    = "prod"
  }

  assert {
    condition = alltrue([
      aws_lb.this.name == "acme-hangarllm-prod",
      aws_lb_target_group.backend.name == "acme-hangarllm-prod-backend",
      aws_elasticache_replication_group.this[0].replication_group_id == "acme-hangarllm-prod-redis",
    ])
    error_message = "Names that fit their AWS limit must keep the plain stack name."
  }
}

run "long_names_are_shortened_to_valid_distinct_names" {
  command = plan

  variables {
    tenant = "a-very-long-tenant-nm"
    env    = "stage-two"
  }

  assert {
    condition = alltrue([
      length(aws_lb.this.name) <= 32,
      length(aws_lb_target_group.gateway.name) <= 32,
      length(aws_lb_target_group.backend.name) <= 32,
      length(aws_lb_target_group.ui.name) <= 32,
      length(aws_elasticache_replication_group.this[0].replication_group_id) <= 40,
      length(distinct([
        aws_lb_target_group.gateway.name,
        aws_lb_target_group.backend.name,
        aws_lb_target_group.ui.name,
      ])) == 3,
      !strcontains(aws_elasticache_replication_group.this[0].replication_group_id, "--"),
    ])
    error_message = "A long stack name must still produce ALB, target group and ElastiCache names within their AWS limits."
  }
}
