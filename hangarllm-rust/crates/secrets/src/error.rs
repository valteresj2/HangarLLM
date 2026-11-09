#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("configured secret manager did not return a secret")]
    ManagedSecretMissing,
    #[error("native secret backend is unavailable for this system")]
    NativeBackendUnavailable,
    #[error("encrypted environment value is missing")]
    MissingCiphertext,
    #[error("ciphertext is not valid base64 for the configured manager")]
    InvalidCiphertext(#[source] Option<base64::DecodeError>),
    #[error("decrypted value is not UTF-8")]
    Utf8(#[source] std::str::Utf8Error),
    #[error(transparent)]
    Client(#[from] hangarllm_http::Error),
    #[error("unsupported OIDC provider or missing build feature")]
    UnsupportedOidc,
    #[error("OIDC reference requires a provider and audience")]
    InvalidOidc,
    #[error("OIDC environment variable is missing")]
    MissingEnvironment,
    #[error("OIDC request failed")]
    OidcHttp(#[source] hangarllm_http::Error),
    #[error("OIDC provider returned HTTP {0}")]
    OidcStatus(u16),
    #[error("OIDC response is invalid")]
    OidcResponse(#[source] hangarllm_http::Error),
    #[error("OIDC file path must be absolute and within the credential allowlist")]
    UnsafeOidcPath,
    #[error("OIDC file could not be read")]
    OidcFile(#[source] std::io::Error),
    #[error("secret cannot be converted to {expected}")]
    TypeMismatch { expected: &'static str },
    #[error("external secret manager failed")]
    ExternalManager(#[source] hangarllm_error::Source),
    #[error("external secret manager read failed")]
    ExternalRead(#[source] hangarllm_error::Source),
    #[cfg(feature = "aws")]
    #[error(transparent)]
    Aws(#[from] hangarllm_secrets_aws::Error),
    #[cfg(feature = "google")]
    #[error(transparent)]
    Google(#[from] hangarllm_secrets_google::Error),
    #[cfg(feature = "hashicorp")]
    #[error(transparent)]
    Hashicorp(#[from] hangarllm_secrets_hashicorp::Error),
    #[cfg(feature = "azure")]
    #[error(transparent)]
    Azure(#[from] hangarllm_secrets_azure::Error),
    #[cfg(feature = "cyberark")]
    #[error(transparent)]
    Cyberark(#[from] hangarllm_secrets_cyberark::Error),
}
