#[derive(Default)]
pub struct AuthServices {
    #[cfg(feature = "aws")]
    pub aws: hangarllm_auth_aws::AwsAuthService,
    #[cfg(feature = "azure")]
    pub azure: hangarllm_auth_azure::AzureAuthService,
    #[cfg(feature = "gcp")]
    pub gcp: hangarllm_auth_gcp::VertexAuth,
}
