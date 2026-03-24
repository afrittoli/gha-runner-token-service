/**
 * Runtime configuration management
 * 
 * In production (containerized deployment):
 * - Configuration is injected at container startup via docker-entrypoint.sh
 * - Values come from Kubernetes ConfigMap and Secret
 * - Available via window.APP_CONFIG
 * 
 * In development (local):
 * - Configuration comes from .env.local file
 * - Vite loads VITE_* environment variables
 * - Falls back to sensible defaults
 */

export interface RuntimeConfig {
  oidc: {
    authority: string;
    clientId: string;
    audience: string;
    redirectUri: string;
    postLogoutRedirectUri: string;
  };
  api: {
    baseUrl: string;
  };
  /** Polling interval for runner data in milliseconds. Default: 30000. */
  refetchInterval: number;
}

declare global {
  interface Window {
    APP_CONFIG?: RuntimeConfig;
  }
}

/**
 * Get runtime configuration
 * Priority: window.APP_CONFIG (production) > import.meta.env (development) > defaults
 */
export function getRuntimeConfig(): RuntimeConfig {
  // In production (containerized), use runtime config injected by docker-entrypoint.sh
  if (window.APP_CONFIG) {
    return window.APP_CONFIG;
  }
  
  // Fallback for local development with .env.local
  // Vite exposes environment variables via import.meta.env
  return {
    oidc: {
      authority: import.meta.env.VITE_OIDC_AUTHORITY || '',
      clientId: import.meta.env.VITE_OIDC_CLIENT_ID || '',
      audience: import.meta.env.VITE_OIDC_AUDIENCE || 'runner-token-service',
      redirectUri: import.meta.env.VITE_OIDC_REDIRECT_URI || `${window.location.origin}/app/callback`,
      postLogoutRedirectUri: import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI || `${window.location.origin}/app`,
    },
    api: {
      baseUrl: import.meta.env.VITE_API_BASE_URL || '',
    },
    refetchInterval: Number(import.meta.env.VITE_REFETCH_INTERVAL ?? 30_000),
  };
}

/**
 * Validate that required configuration is present
 * Throws an error if critical configuration is missing
 */
export function validateConfig(config: RuntimeConfig): void {
  const errors: string[] = [];

  if (!config.oidc.authority) {
    errors.push('OIDC authority is required');
  }

  if (!config.oidc.clientId) {
    errors.push('OIDC client ID is required');
  }

  if (!config.oidc.audience) {
    errors.push('OIDC audience is required');
  }

  if (errors.length > 0) {
    throw new Error(`Configuration validation failed:\n${errors.join('\n')}`);
  }
}
