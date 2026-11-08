output "lb_ip" {
  description = "Global anycast IP of the external load balancer."
  value       = module.hangarllm.lb_ip
}

output "lb_url" {
  description = "Proxy URL. Dashboard at /, API at /v1/*."
  value       = module.hangarllm.lb_url
}

output "gateway_service_url" {
  description = "Default Cloud Run URL for the gateway (bypasses the LB)."
  value       = module.hangarllm.gateway_service_url
}

output "backend_service_url" {
  description = "Default Cloud Run URL for the backend (bypasses the LB)."
  value       = module.hangarllm.backend_service_url
}

output "ui_service_url" {
  description = "Default Cloud Run URL for the UI (bypasses the LB)."
  value       = module.hangarllm.ui_service_url
}

output "cloudsql_writer_ip" {
  description = "Private IP of the Cloud SQL writer."
  value       = module.hangarllm.cloudsql_writer_ip
}

output "cloudsql_reader_ip" {
  description = "Private IP of the Cloud SQL read replica."
  value       = module.hangarllm.cloudsql_reader_ip
}

output "redis_endpoint" {
  description = "Memorystore Redis endpoint."
  value       = module.hangarllm.redis_endpoint
}

output "redis_host" {
  description = "Memorystore Redis host."
  value       = module.hangarllm.redis_host
}

output "redis_port" {
  description = "Memorystore Redis port."
  value       = module.hangarllm.redis_port
}

output "redis_server_ca_pem" {
  description = "Memorystore server CA PEM."
  value       = module.hangarllm.redis_server_ca_pem
}

output "db_username" {
  description = "Cloud SQL application username."
  value       = module.hangarllm.db_username
}

output "db_name" {
  description = "Cloud SQL database name."
  value       = module.hangarllm.db_name
}

output "gcs_bucket" {
  description = "GCS bucket name."
  value       = module.hangarllm.gcs_bucket
}

output "master_key_secret_id" {
  description = "Secret Manager resource ID holding HANGARLLM_MASTER_KEY."
  value       = module.hangarllm.master_key_secret_id
}

output "db_password_secret_id" {
  description = "Secret Manager resource ID holding the Cloud SQL app-user password."
  value       = module.hangarllm.db_password_secret_id
}

output "runtime_service_account_email" {
  description = "Runtime service account email."
  value       = module.hangarllm.runtime_service_account_email
}

output "migration_run_command" {
  description = "Break-glass command to re-run the one-off migration job."
  value       = module.hangarllm.migration_run_command
}
