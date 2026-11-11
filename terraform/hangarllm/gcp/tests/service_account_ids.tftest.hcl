mock_provider "google" {
  mock_resource "google_redis_instance" {
    defaults = {
      host = "10.0.0.4"
      port = 6379
      server_ca_certs = [{
        cert = "-----BEGIN CERTIFICATE-----\nmock\n-----END CERTIFICATE-----"
      }]
    }
  }
}

mock_provider "google-beta" {}
mock_provider "random" {}

variables {
  image_tag          = "v9.9.9"
  project_id         = "test-project"
  allow_plaintext_lb = true
  image_registry     = "us-central1-docker.pkg.dev/test-project/hangarllm"
}

run "ids_that_fit_keep_the_plain_name" {
  command = plan

  variables {
    tenant = "acme"
    env    = "prod"
  }

  assert {
    condition = alltrue([
      google_service_account.runtime.account_id == "acme-hangarllm-prod-runtime",
      google_service_account.ui_runtime[0].account_id == "acme-hangarllm-prod-ui-runtime",
    ])
    error_message = "Service account ids that fit in 30 characters must keep the plain stack name."
  }
}

run "long_names_are_shortened_to_valid_distinct_ids" {
  command = plan

  variables {
    tenant = "a-very-long-tenant-nm"
    env    = "stage-two"
  }

  assert {
    condition = alltrue([
      length(google_service_account.runtime.account_id) <= 30,
      length(google_service_account.ui_runtime[0].account_id) <= 30,
      google_service_account.runtime.account_id != google_service_account.ui_runtime[0].account_id,
      can(regex("^a-very-long-.*-runtime$", google_service_account.runtime.account_id)),
      can(regex("^a-very-long-.*-ui-runtime$", google_service_account.ui_runtime[0].account_id)),
    ])
    error_message = "A long stack name must still produce GCP service account ids of at most 30 characters."
  }
}
