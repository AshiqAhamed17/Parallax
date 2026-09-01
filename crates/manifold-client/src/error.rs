#[derive(Debug, thiserror::Error)]
pub enum ManifoldClientError {
    #[error("manifold api request failed: {0}")]
    Http(#[from] reqwest::Error),
}
