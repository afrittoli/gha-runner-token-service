// Runtime configuration injected at container startup
// This file is processed by envsubst in docker-entrypoint.sh
// Environment variables are substituted with actual values from Kubernetes ConfigMap/Secret
window.APP_CONFIG = {
  oidc: {
    authority: '${OIDC_AUTHORITY}',
    clientId: '${OIDC_CLIENT_ID}',
    audience: '${OIDC_AUDIENCE}',
    redirectUri: '${OIDC_REDIRECT_URI}',
    postLogoutRedirectUri: '${OIDC_POST_LOGOUT_REDIRECT_URI}',
  },
  api: {
    baseUrl: '${API_BASE_URL}',
  },
};
