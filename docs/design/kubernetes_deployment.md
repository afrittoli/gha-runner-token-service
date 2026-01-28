# GHARTS Kubernetes Deployment Design

## Overview

This document outlines the design for deploying GHARTS (GitHub Actions Runner Token Service) as containers on Kubernetes, with support for cloud-based databases and serverless deployment patterns.

## Architecture

### Deployment Model

**Separate Frontend/Backend Deployment** (Recommended)
- Independent scaling for frontend and backend
- Frontend served by Nginx for optimal static file delivery
- Backend focused on API processing
- Better resource utilization and cost optimization

```
┌─────────────────────────────────────┐
│      Frontend Pod (Nginx)           │
│  ┌──────────────────────────────┐  │
│  │   Nginx                      │  │
│  │   - Serves React SPA         │  │
│  │   - Proxies /api to backend  │  │
│  │   - Static asset caching     │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         └─── Backend Service

┌─────────────────────────────────────┐
│      Backend Pod (FastAPI)          │
│  ┌──────────────────────────────┐  │
│  │   FastAPI + Uvicorn          │  │
│  │   - API endpoints only       │  │
│  │   - Business logic           │  │
│  │   - Database access          │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         ├─── PostgreSQL (RDS/Aurora)
         └─── GitHub API
```

**Scaling Strategy:**
- Frontend: Scale based on HTTP requests, static content delivery
- Backend: Scale based on API processing, database connections
- Typical ratio: 2-3 frontend pods per backend pod

### Container Images

1. **Backend Image**: `ghcr.io/[org]/gharts-backend:v1.0.0`
   - Python 3.11 slim base
   - FastAPI + Uvicorn
   - API endpoints only
   - Multi-architecture (amd64, arm64)

2. **Frontend Image**: `ghcr.io/[org]/gharts-frontend:v1.0.0`
   - Nginx alpine base
   - React SPA build artifacts
   - Optimized for static file serving
   - Multi-architecture (amd64, arm64)

## Component Design

### 1. Legacy Dashboard Removal

**Files to Remove:**
- [`app/templates/dashboard.html`](../../app/templates/dashboard.html) - 930 lines of legacy HTML dashboard
- Dashboard-related routes in [`app/main.py`](../../app/main.py)
- `enable_new_dashboard` config flag from [`app/config.py`](../../app/config.py)

**Migration Path:**
- No migration needed - React dashboard is feature-complete
- Update documentation to reference `/app` path only

### 2. Backend Dockerfile

**Location**: `Dockerfile.backend`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Create directories
RUN mkdir -p /app/data /app/logs

# Non-root user
RUN useradd -m -u 1000 gharts && \
    chown -R gharts:gharts /app
USER gharts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key Features:**
- Minimal Python 3.11 slim base
- Non-root user for security
- Health check endpoint
- Proper signal handling for graceful shutdown
- Optimized for API processing only

### 3. Frontend Dockerfile

**Location**: `frontend/Dockerfile`

**Multi-stage Build:**

```dockerfile
# Stage 1: Build React application
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build production bundle
RUN npm run build

# Stage 2: Nginx runtime
FROM nginx:1.25-alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Create non-root user
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

**Nginx Configuration** (`frontend/nginx.conf`):

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 10M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml+rss
               application/rss+xml font/truetype font/opentype
               application/vnd.ms-fontobject image/svg+xml;

    include /etc/nginx/conf.d/*.conf;
}
```

**Default Site Configuration** (`frontend/default.conf`):

```nginx
server {
    listen 8080;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    # API proxy to backend
    location /api/ {
        proxy_pass http://gharts-backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Static assets with caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA routing - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
    }
}
```

**Key Features:**
- Multi-stage build minimizes image size
- Nginx optimized for static file serving
- Gzip compression enabled
- Security headers configured
- API proxy to backend service
- SPA routing support
- Static asset caching
- Non-root user

### 4. Database Configuration

**Enhanced [`app/config.py`](../../app/config.py):**

```python
# Database Configuration
database_url: str = Field(
    default="sqlite:///./runner_service.db",
    description="Database connection URL (PostgreSQL, MySQL, SQLite)"
)
database_pool_size: int = Field(
    default=5,
    description="Database connection pool size"
)
database_max_overflow: int = Field(
    default=10,
    description="Maximum overflow connections"
)
database_pool_timeout: int = Field(
    default=30,
    description="Connection pool timeout in seconds"
)
database_pool_recycle: int = Field(
    default=3600,
    description="Recycle connections after N seconds"
)
database_ssl_mode: Optional[str] = Field(
    default=None,
    description="SSL mode for database connection (require, verify-ca, verify-full)"
)
database_ssl_ca: Optional[Path] = Field(
    default=None,
    description="Path to SSL CA certificate for database"
)
```

**AWS RDS/Aurora Support:**
- PostgreSQL connection string: `postgresql://user:pass@host:5432/dbname?sslmode=require`
- Aurora DSQL connection string: `postgresql://user:pass@cluster.region.rds.amazonaws.com:5432/dbname`
- SSL/TLS enabled by default for cloud databases
- Connection pooling optimized for serverless patterns

**Database Initialization:**
- Alembic migrations run on startup
- Idempotent schema creation
- Support for read replicas (future enhancement)

### 5. Bootstrap Admin Account

**Design Philosophy:**
- Temporary local admin for initial setup
- Auto-disables after first OIDC admin login
- Password never stored in database
- Secure by default

**Implementation:**

**New Config Fields:**
```python
# Bootstrap Admin Configuration
bootstrap_admin_enabled: bool = Field(
    default=True,
    description="Enable bootstrap admin account for initial setup"
)
bootstrap_admin_username: str = Field(
    default="admin",
    description="Bootstrap admin username"
)
bootstrap_admin_password: Optional[str] = Field(
    default=None,
    description="Bootstrap admin password (auto-generated if not provided)"
)
bootstrap_admin_password_file: Optional[Path] = Field(
    default=Path("/tmp/gharts-admin-password.txt"),
    description="File to write auto-generated password"
)
```

**Startup Logic** (new file: `app/bootstrap.py`):

```python
class BootstrapAdmin:
    """Manages temporary bootstrap admin account."""
    
    def __init__(self):
        self._password: Optional[str] = None
        self._enabled: bool = True
        self._team_id: Optional[int] = None
    
    async def initialize(self, db: Session, settings: Settings):
        """Initialize bootstrap admin on startup."""
        if not settings.bootstrap_admin_enabled:
            return
        
        # Check if any OIDC admin exists
        oidc_admin = db.query(User).filter(
            User.is_admin == True,
            User.auth_provider == "oidc"
        ).first()
        
        if oidc_admin:
            logger.info("OIDC admin exists, bootstrap admin disabled")
            self._enabled = False
            return
        
        # Create default admin team
        admin_team = self._ensure_admin_team(db)
        self._team_id = admin_team.id
        
        # Set or generate password
        if settings.bootstrap_admin_password:
            self._password = settings.bootstrap_admin_password
            logger.info("Bootstrap admin using provided password")
        else:
            self._password = secrets.token_urlsafe(32)
            logger.warning(f"Bootstrap admin password: {self._password}")
            
            # Write to file if configured
            if settings.bootstrap_admin_password_file:
                settings.bootstrap_admin_password_file.write_text(
                    self._password
                )
                logger.info(
                    f"Bootstrap password written to {settings.bootstrap_admin_password_file}"
                )
        
        logger.info(
            f"Bootstrap admin enabled: username={settings.bootstrap_admin_username}"
        )
    
    def _ensure_admin_team(self, db: Session) -> Team:
        """Create default admin team with unrestricted access."""
        team = db.query(Team).filter(
            Team.name == "bootstrap-admins"
        ).first()
        
        if not team:
            team = Team(
                name="bootstrap-admins",
                description="Temporary admin team for initial setup",
                is_admin=True
            )
            db.add(team)
            
            # Create unrestricted label policy
            policy = LabelPolicy(
                team_id=team.id,
                allowed_labels=[],
                label_patterns=[".*"],  # Allow all labels
                max_runners=None,  # Unlimited
                require_ephemeral=False
            )
            db.add(policy)
            db.commit()
        
        return team
    
    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify bootstrap admin credentials."""
        if not self._enabled:
            return False
        
        settings = get_settings()
        return (
            username == settings.bootstrap_admin_username and
            password == self._password
        )
    
    async def on_oidc_admin_login(self, db: Session):
        """Disable bootstrap admin after first OIDC admin login."""
        if not self._enabled:
            return
        
        logger.info("First OIDC admin login detected, disabling bootstrap admin")
        self._enabled = False
        self._password = None  # Clear from memory
        
        # Mark bootstrap team as inactive
        if self._team_id:
            team = db.query(Team).get(self._team_id)
            if team:
                team.is_active = False
                db.commit()

# Global instance
bootstrap_admin = BootstrapAdmin()
```

**Authentication Flow:**

```mermaid
graph TD
    A[Request] --> B{Auth Type?}
    B -->|Bearer Token| C[OIDC Validation]
    B -->|Basic Auth| D{Bootstrap Enabled?}
    D -->|Yes| E[Verify Bootstrap Creds]
    D -->|No| F[Reject]
    E -->|Valid| G[Grant Admin Access]
    E -->|Invalid| F
    C -->|Valid OIDC| H{First Admin?}
    H -->|Yes| I[Disable Bootstrap]
    H -->|No| J[Continue]
    I --> K[Grant Access]
    J --> K
    C -->|Invalid| F
    G --> K
```

### 6. Helm Chart Structure

**Location**: `charts/gharts/`

```
charts/gharts/
├── Chart.yaml
├── values.yaml
├── values-production.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── backend-hpa.yaml
│   ├── backend-pdb.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   ├── frontend-hpa.yaml
│   ├── frontend-pdb.yaml
│   ├── ingress.yaml
│   ├── httproute.yaml
│   ├── gateway.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── serviceaccount.yaml
│   ├── networkpolicy.yaml
│   └── tests/
│       └── test-connection.yaml
└── README.md
```

**Chart.yaml:**
```yaml
apiVersion: v2
name: gharts
description: GitHub Actions Runner Token Service
type: application
version: 1.0.0
appVersion: "1.0.0"
keywords:
  - github
  - actions
  - runners
  - oidc
home: https://github.com/[org]/gha-runner-token-service
sources:
  - https://github.com/[org]/gha-runner-token-service
maintainers:
  - name: GHARTS Team
    email: team@example.com
```

**values.yaml** (key sections):

```yaml
# Backend configuration
backend:
  image:
    repository: ghcr.io/[org]/gharts-backend
    pullPolicy: IfNotPresent
    tag: ""  # Defaults to chart appVersion
  
  replicaCount: 2
  
  resources:
    limits:
      cpu: 1000m
      memory: 512Mi
    requests:
      cpu: 200m
      memory: 256Mi
  
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80
  
  service:
    type: ClusterIP
    port: 8000
    annotations: {}

# Frontend configuration
frontend:
  image:
    repository: ghcr.io/[org]/gharts-frontend
    pullPolicy: IfNotPresent
    tag: ""  # Defaults to chart appVersion
  
  replicaCount: 3
  
  resources:
    limits:
      cpu: 200m
      memory: 128Mi
    requests:
      cpu: 50m
      memory: 64Mi
  
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 30
    targetCPUUtilizationPercentage: 60
    targetMemoryUtilizationPercentage: 70
  
  service:
    type: ClusterIP
    port: 8080
    annotations: {}

imagePullSecrets: []

# Database configuration
database:
  # Connection URL (required)
  url: ""
  # Example: postgresql://user:pass@host:5432/dbname?sslmode=require
  
  # Connection pool settings
  poolSize: 5
  maxOverflow: 10
  poolTimeout: 30
  poolRecycle: 3600
  
  # SSL/TLS configuration
  sslMode: "require"  # require, verify-ca, verify-full
  sslCA:
    enabled: false
    # Mount CA certificate from secret
    secretName: ""
    secretKey: "ca.crt"

# GitHub App configuration
github:
  appId: ""
  installationId: ""
  organization: ""
  apiUrl: "https://api.github.com"
  
  # Private key configuration
  privateKey:
    # Option 1: Reference existing secret
    existingSecret: ""
    secretKey: "private-key.pem"
    
    # Option 2: Provide inline (not recommended for production)
    value: ""

# OIDC configuration
oidc:
  issuer: ""
  audience: ""
  jwksUrl: ""
  enabled: true

# Bootstrap admin configuration
bootstrap:
  enabled: true
  username: "admin"
  # Password options:
  # 1. Auto-generate and store in secret (default)
  # 2. Provide via existingSecret
  # 3. Provide via password field (not recommended)
  password: ""
  existingSecret: ""
  secretKey: "admin-password"

# Traffic routing configuration
# Choose between Ingress (legacy) or Gateway API (recommended)
routing:
  # Type: "ingress" or "gateway"
  type: "gateway"

# Ingress configuration (legacy, for backward compatibility)
ingress:
  enabled: false
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: gharts.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: gharts-tls
      hosts:
        - gharts.example.com

# Gateway API configuration (recommended)
gateway:
  enabled: true
  
  # Gateway configuration
  # Set create: false to use existing gateway
  create: true
  name: gharts-gateway
  gatewayClassName: "istio"  # or "nginx", "contour", etc.
  
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      allowedRoutes:
        namespaces:
          from: Same
    - name: https
      protocol: HTTPS
      port: 443
      allowedRoutes:
        namespaces:
          from: Same
      tls:
        mode: Terminate
        certificateRefs:
          - name: gharts-tls
  
  # HTTPRoute configuration
  httpRoute:
    hostnames:
      - "gharts.example.com"
    
    # Optional: TLS redirect
    tlsRedirect: true
    
    # Route rules
    rules:
      - matches:
          - path:
              type: PathPrefix
              value: /api/
        backendRefs:
          - name: gharts-backend
            port: 8000
      
      - matches:
          - path:
              type: PathPrefix
              value: /
        backendRefs:
          - name: gharts-frontend
            port: 8080

# Security context
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

containerSecurityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true

# Persistence for logs (optional)
persistence:
  enabled: false
  storageClass: ""
  accessMode: ReadWriteOnce
  size: 1Gi

# Pod disruption budget
podDisruptionBudget:
  enabled: true
  minAvailable: 1

# Network policy
networkPolicy:
  enabled: false
  policyTypes:
    - Ingress
    - Egress

# Service account
serviceAccount:
  create: true
  annotations: {}
  name: ""

# Additional environment variables
extraEnv: []
# - name: CUSTOM_VAR
#   value: "custom-value"

# Additional secrets
extraSecrets: {}

# Node selector
nodeSelector: {}

# Tolerations
tolerations: []

# Affinity
affinity: {}
```

**Deployment Template** (`templates/deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "gharts.fullname" . }}
  labels:
    {{- include "gharts.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "gharts.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
        checksum/secret: {{ include (print $.Template.BasePath "/secret.yaml") . | sha256sum }}
      labels:
        {{- include "gharts.selectorLabels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "gharts.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
      - name: {{ .Chart.Name }}
        securityContext:
          {{- toYaml .Values.containerSecurityContext | nindent 12 }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - name: http
          containerPort: 8000
          protocol: TCP
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          {{- toYaml .Values.resources | nindent 12 }}
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: {{ include "gharts.fullname" . }}
              key: database-url
        - name: GITHUB_APP_ID
          valueFrom:
            configMapKeyRef:
              name: {{ include "gharts.fullname" . }}
              key: github-app-id
        - name: GITHUB_APP_INSTALLATION_ID
          valueFrom:
            configMapKeyRef:
              name: {{ include "gharts.fullname" . }}
              key: github-installation-id
        - name: GITHUB_ORG
          valueFrom:
            configMapKeyRef:
              name: {{ include "gharts.fullname" . }}
              key: github-org
        - name: OIDC_ISSUER
          valueFrom:
            configMapKeyRef:
              name: {{ include "gharts.fullname" . }}
              key: oidc-issuer
        - name: OIDC_AUDIENCE
          valueFrom:
            configMapKeyRef:
              name: {{ include "gharts.fullname" . }}
              key: oidc-audience
        - name: OIDC_JWKS_URL
          valueFrom:
            configMapKeyRef:
              name: {{ include "gharts.fullname" . }}
              key: oidc-jwks-url
        - name: BOOTSTRAP_ADMIN_USERNAME
          value: {{ .Values.bootstrap.username | quote }}
        - name: BOOTSTRAP_ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ include "gharts.bootstrapSecretName" . }}
              key: {{ .Values.bootstrap.secretKey }}
        {{- with .Values.extraEnv }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
        volumeMounts:
        - name: github-private-key
          mountPath: /secrets/github
          readOnly: true
        - name: tmp
          mountPath: /tmp
        - name: logs
          mountPath: /app/logs
        {{- if .Values.persistence.enabled }}
        - name: data
          mountPath: /app/data
        {{- end }}
      volumes:
      - name: github-private-key
        secret:
          secretName: {{ include "gharts.githubSecretName" . }}
          items:
          - key: {{ .Values.github.privateKey.secretKey }}
            path: private-key.pem
            mode: 0400
      - name: tmp
        emptyDir: {}
      - name: logs
        emptyDir: {}
      {{- if .Values.persistence.enabled }}
      - name: data
        persistentVolumeClaim:
          claimName: {{ include "gharts.fullname" . }}
      {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

**Frontend Deployment Template** (`templates/frontend-deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "gharts.fullname" . }}-frontend
  labels:
    {{- include "gharts.labels" . | nindent 4 }}
    app.kubernetes.io/component: frontend
spec:
  {{- if not .Values.frontend.autoscaling.enabled }}
  replicas: {{ .Values.frontend.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "gharts.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: frontend
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
      labels:
        {{- include "gharts.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: frontend
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "gharts.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
      - name: frontend
        securityContext:
          {{- toYaml .Values.containerSecurityContext | nindent 12 }}
        image: "{{ .Values.frontend.image.repository }}:{{ .Values.frontend.image.tag | default .Chart.AppVersion }}"
        imagePullPolicy: {{ .Values.frontend.image.pullPolicy }}
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          {{- toYaml .Values.frontend.resources | nindent 12 }}
        volumeMounts:
        - name: nginx-cache
          mountPath: /var/cache/nginx
        - name: nginx-run
          mountPath: /var/run
      volumes:
      - name: nginx-cache
        emptyDir: {}
      - name: nginx-run
        emptyDir: {}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

**Backend Service Template** (`templates/backend-service.yaml`):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "gharts.fullname" . }}-backend
  labels:
    {{- include "gharts.labels" . | nindent 4 }}
    app.kubernetes.io/component: backend
spec:
  type: {{ .Values.backend.service.type }}
  ports:
    - port: {{ .Values.backend.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "gharts.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: backend
```

**Frontend Service Template** (`templates/frontend-service.yaml`):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "gharts.fullname" . }}-frontend
  labels:
    {{- include "gharts.labels" . | nindent 4 }}
    app.kubernetes.io/component: frontend
spec:
  type: {{ .Values.frontend.service.type }}
  ports:
    - port: {{ .Values.frontend.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "gharts.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: frontend
```
**Gateway Template** (`templates/gateway.yaml`):

```yaml
{{- if and .Values.gateway.enabled .Values.gateway.create (eq .Values.routing.type "gateway") }}
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: {{ .Values.gateway.name | default (include "gharts.fullname" .) }}
  labels:
    {{- include "gharts.labels" . | nindent 4 }}
spec:
  gatewayClassName: {{ .Values.gateway.gatewayClassName }}
  listeners:
  {{- range .Values.gateway.listeners }}
  - name: {{ .name }}
    protocol: {{ .protocol }}
    port: {{ .port }}
    {{- if .hostname }}
    hostname: {{ .hostname }}
    {{- end }}
    {{- if .tls }}
    tls:
      mode: {{ .tls.mode }}
      {{- if .tls.certificateRefs }}
      certificateRefs:
      {{- range .tls.certificateRefs }}
      - name: {{ .name }}
        {{- if .namespace }}
        namespace: {{ .namespace }}
        {{- end }}
      {{- end }}
      {{- end }}
    {{- end }}
    allowedRoutes:
      {{- toYaml .allowedRoutes | nindent 6 }}
  {{- end }}
{{- end }}
```

**HTTPRoute Template** (`templates/httproute.yaml`):

```yaml
{{- if and .Values.gateway.enabled (eq .Values.routing.type "gateway") }}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ include "gharts.fullname" . }}
  labels:
    {{- include "gharts.labels" . | nindent 4 }}
spec:
  parentRefs:
  - name: {{ .Values.gateway.name | default (include "gharts.fullname" .) }}
    {{- if .Values.gateway.namespace }}
    namespace: {{ .Values.gateway.namespace }}
    {{- end }}
  hostnames:
  {{- range .Values.gateway.httpRoute.hostnames }}
  - {{ . | quote }}
  {{- end }}
  rules:
  {{- if .Values.gateway.httpRoute.tlsRedirect }}
  # HTTP to HTTPS redirect
  - matches:
    - path:
        type: PathPrefix
        value: /
    filters:
    - type: RequestRedirect
      requestRedirect:
        scheme: https
        statusCode: 301
  {{- end }}
  
  # API routes to backend
  - matches:
    - path:
        type: PathPrefix
        value: /api/
    backendRefs:
    - name: {{ include "gharts.fullname" . }}-backend
      port: {{ .Values.backend.service.port }}
      weight: 100
  
  # Frontend routes (catch-all)
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: {{ include "gharts.fullname" . }}-frontend
      port: {{ .Values.frontend.service.port }}
      weight: 100
{{- end }}
```

**Ingress Template** (`templates/ingress.yaml`) - Updated for conditional rendering:

```yaml
{{- if and .Values.ingress.enabled (eq .Values.routing.type "ingress") }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "gharts.fullname" . }}
  labels:
    {{- include "gharts.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .Values.ingress.className }}
  ingressClassName: {{ .Values.ingress.className }}
  {{- end }}
  {{- if .Values.ingress.tls }}
  tls:
  {{- range .Values.ingress.tls }}
  - hosts:
    {{- range .hosts }}
    - {{ . | quote }}
    {{- end }}
    secretName: {{ .secretName }}
  {{- end }}
  {{- end }}
  rules:
  {{- range .Values.ingress.hosts }}
  - host: {{ .host | quote }}
    http:
      paths:
      # API routes to backend
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: {{ include "gharts.fullname" $ }}-backend
            port:
              number: {{ $.Values.backend.service.port }}
      # Frontend routes (catch-all)
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {{ include "gharts.fullname" $ }}-frontend
            port:
              number: {{ $.Values.frontend.service.port }}
  {{- end }}
{{- end }}
```


### 7. CI/CD Workflows

#### Docker Build Test Workflow

**Location**: `.github/workflows/docker-build.yml`

```yaml
name: Docker Build Tests

on:
  push:
    branches: [main]
    paths:
      - 'app/**'
      - 'frontend/**'
      - 'Dockerfile.backend'
      - 'requirements.txt'
      - '.github/workflows/docker-build.yml'
  pull_request:
    branches: [main]
    paths:
      - 'app/**'
      - 'frontend/**'
      - 'Dockerfile.backend'
      - 'requirements.txt'
      - '.github/workflows/docker-build.yml'

jobs:
  build-backend:
    name: Build Backend Image
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build backend image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.backend
          push: false
          tags: gharts-backend:test
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
      
      - name: Test image
        run: |
          docker run --rm gharts-backend:test python -c "import app; print('Backend OK')"
  
  build-size-check:
    name: Check Image Size
    runs-on: ubuntu-latest
    needs: build-backend
    steps:
      - uses: actions/checkout@v4
      
      - name: Build and check size
        run: |
          docker build -f Dockerfile.backend -t gharts-backend:test .
          SIZE=$(docker images gharts-backend:test --format "{{.Size}}")
          echo "Image size: $SIZE"
          
          # Warn if image is larger than 500MB
          SIZE_MB=$(docker images gharts-backend:test --format "{{.Size}}" | sed 's/MB//')
          if [ $(echo "$SIZE_MB > 500" | bc) -eq 1 ]; then
            echo "::warning::Image size $SIZE exceeds 500MB threshold"
          fi
```

#### Release Workflow

**Location**: `.github/workflows/release.yml`

```yaml
name: Release

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to release (e.g., 1.0.0)'
        required: true
        type: string
      sha:
        description: 'Git SHA to release (defaults to latest main)'
        required: false
        type: string
        default: ''

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  validate:
    name: Validate Release
    runs-on: ubuntu-latest
    outputs:
      sha: ${{ steps.get-sha.outputs.sha }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ inputs.sha || 'main' }}
          fetch-depth: 0
      
      - name: Get SHA
        id: get-sha
        run: |
          if [ -n "${{ inputs.sha }}" ]; then
            echo "sha=${{ inputs.sha }}" >> $GITHUB_OUTPUT
          else
            echo "sha=$(git rev-parse HEAD)" >> $GITHUB_OUTPUT
          fi
      
      - name: Check if tag exists
        run: |
          if git rev-parse "v${{ inputs.version }}" >/dev/null 2>&1; then
            echo "::error::Tag v${{ inputs.version }} already exists"
            exit 1
          fi
      
      - name: Validate version format
        run: |
          if ! echo "${{ inputs.version }}" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$'; then
            echo "::error::Invalid version format. Use semver (e.g., 1.0.0 or 1.0.0-beta.1)"
            exit 1
          fi

  build-and-push:
    name: Build and Push Images
    runs-on: ubuntu-latest
    needs: validate
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ needs.validate.outputs.sha }}
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}},value=${{ inputs.version }}
            type=semver,pattern={{major}}.{{minor}},value=${{ inputs.version }}
            type=semver,pattern={{major}},value=${{ inputs.version }}
            type=sha,prefix=,format=long
      
      - name: Extract backend metadata
        id: meta-backend
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-backend
          tags: |
            type=semver,pattern={{version}},value=${{ inputs.version }}
            type=semver,pattern={{major}}.{{minor}},value=${{ inputs.version }}
            type=semver,pattern={{major}},value=${{ inputs.version }}
            type=sha,prefix=,format=long
      
      - name: Extract frontend metadata
        id: meta-frontend
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-frontend
          tags: |
            type=semver,pattern={{version}},value=${{ inputs.version }}
            type=semver,pattern={{major}}.{{minor}},value=${{ inputs.version }}
            type=semver,pattern={{major}},value=${{ inputs.version }}
            type=sha,prefix=,format=long
      
      - name: Build and push backend image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.backend
          push: true
          tags: ${{ steps.meta-backend.outputs.tags }}
          labels: ${{ steps.meta-backend.outputs.labels }}
          platforms: linux/amd64,linux/arm64
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            VERSION=${{ inputs.version }}
            COMMIT_SHA=${{ needs.validate.outputs.sha }}
      
      - name: Build and push frontend image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: ./frontend/Dockerfile
          push: true
          tags: ${{ steps.meta-frontend.outputs.tags }}
          labels: ${{ steps.meta-frontend.outputs.labels }}
          platforms: linux/amd64,linux/arm64
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            VERSION=${{ inputs.version }}
            COMMIT_SHA=${{ needs.validate.outputs.sha }}

  update-helm-chart:
    name: Update and Publish Helm Chart
    runs-on: ubuntu-latest
    needs: [validate, build-and-push]
    permissions:
      contents: write
      packages: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ needs.validate.outputs.sha }}
          token: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Install Helm
        uses: azure/setup-helm@v3
        with:
          version: '3.13.0'
      
      - name: Update Chart version
        run: |
          sed -i "s/^version:.*/version: ${{ inputs.version }}/" charts/gharts/Chart.yaml
          sed -i "s/^appVersion:.*/appVersion: \"${{ inputs.version }}\"/" charts/gharts/Chart.yaml
      
      - name: Package Helm chart
        run: |
          helm package charts/gharts -d .helm-releases
      
      - name: Log in to Container Registry
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | helm registry login ${{ env.REGISTRY }} --username ${{ github.actor }} --password-stdin
      
      - name: Push Helm chart
        run: |
          helm push .helm-releases/gharts-${{ inputs.version }}.tgz oci://${{ env.REGISTRY }}/${{ github.repository_owner }}/charts

  create-release:
    name: Create GitHub Release
    runs-on: ubuntu-latest
    needs: [validate, build-and-push, update-helm-chart]
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ needs.validate.outputs.sha }}
          fetch-depth: 0
      
      - name: Generate release notes
        id: notes
        run: |
          # Get previous tag
          PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
          
          if [ -z "$PREV_TAG" ]; then
            echo "First release"
            NOTES="Initial release of GHARTS v${{ inputs.version }}"
          else
            echo "Generating notes from $PREV_TAG to HEAD"
            NOTES=$(git log ${PREV_TAG}..HEAD --pretty=format:"- %s (%h)" --no-merges)
          fi
          
          # Create release notes file
          cat > release-notes.md << EOF
          # GHARTS v${{ inputs.version }}
          
          ## Container Images
          
          - Backend: \`${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ inputs.version }}\`
          - Helm Chart: \`oci://${{ env.REGISTRY }}/${{ github.repository_owner }}/charts/gharts:${{ inputs.version }}\`
          
          ## Installation
          
          \`\`\`bash
          # Using Helm
          helm install gharts oci://${{ env.REGISTRY }}/${{ github.repository_owner }}/charts/gharts --version ${{ inputs.version }}
          
          # Using Docker
          docker pull ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ inputs.version }}
          \`\`\`
          
          ## Changes
          
          ${NOTES}
          
          ## Full Changelog
          
          **Full Changelog**: https://github.com/${{ github.repository }}/compare/${PREV_TAG}...v${{ inputs.version }}
          EOF
          
          cat release-notes.md
      
      - name: Create Git tag
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git tag -a "v${{ inputs.version }}" -m "Release v${{ inputs.version }}"
          git push origin "v${{ inputs.version }}"
      
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: v${{ inputs.version }}
          name: v${{ inputs.version }}
          body_path: release-notes.md
          draft: false
          prerelease: ${{ contains(inputs.version, '-') }}
          generate_release_notes: true
```

## Deployment Guide

### Prerequisites

1. **Kubernetes Cluster**: v1.24+
2. **Helm**: v3.13+
3. **Database**: PostgreSQL 13+ (AWS RDS/Aurora recommended)
4. **GitHub App**: Configured with appropriate permissions
5. **OIDC Provider**: Auth0, Okta, or similar

### Quick Start

1. **Add Helm repository:**
```bash
helm repo add gharts oci://ghcr.io/[org]/charts
helm repo update
```

2. **Create values file** (`values-prod.yaml`):
```yaml
backend:
  image:
    tag: "1.0.0"
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20

frontend:
  image:
    tag: "1.0.0"
  replicaCount: 5
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 30

database:
  url: "postgresql://user:pass@rds-endpoint:5432/gharts?sslmode=require"
  poolSize: 10

github:
  appId: "123456"
  installationId: "12345678"
  organization: "your-org"
  privateKey:
    existingSecret: "github-app-key"
    secretKey: "private-key.pem"

oidc:
  issuer: "https://your-tenant.auth0.com"
  audience: "gharts-api"
  jwksUrl: "https://your-tenant.auth0.com/.well-known/jwks.json"

bootstrap:
  enabled: true
  username: "admin"

ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: gharts.example.com
      paths:

## Gateway API vs Ingress

### Why Gateway API?

The Kubernetes Gateway API is the successor to Ingress and provides several advantages:

**Benefits:**
1. **Role-oriented design**: Separates infrastructure (Gateway) from application routing (HTTPRoute)
2. **More expressive**: Better support for advanced routing, traffic splitting, header manipulation
3. **Portable**: Works across different implementations (Istio, Nginx, Contour, etc.)
4. **Type-safe**: Strongly typed API with better validation
5. **Future-proof**: Active development, will replace Ingress long-term

**Gateway API Features:**
- HTTP/HTTPS routing with advanced matching
- Traffic splitting for canary deployments
- Request/response header manipulation
- Redirects and rewrites
- Cross-namespace routing
- Multiple protocols (HTTP, HTTPS, TCP, UDP, gRPC)

### Choosing Between Gateway API and Ingress

**Use Gateway API when:**
- Starting a new deployment
- Your cluster supports Gateway API (v1.0+)
- You need advanced routing features
- You want future-proof infrastructure

**Use Ingress when:**
- Working with older Kubernetes clusters (<1.24)
- Your organization has existing Ingress infrastructure
- You need backward compatibility
- Gateway API is not yet available in your environment

### Migration Path

**From Ingress to Gateway API:**

1. **Install Gateway API CRDs:**
```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.0.0/standard-install.yaml
```

2. **Deploy Gateway controller** (example with Istio):
```bash
helm install istio-gateway istio/gateway
```

3. **Update Helm values:**
```yaml
# Switch from Ingress to Gateway API
routing:
  type: "gateway"  # Changed from "ingress"

gateway:
  enabled: true
  gatewayClassName: "istio"
  
ingress:
  enabled: false  # Disable old Ingress
```

4. **Apply changes:**
```bash
helm upgrade gharts gharts/gharts -f values-gateway.yaml
```

5. **Verify routing:**
```bash
kubectl get gateway,httproute -n gharts
kubectl describe httproute gharts -n gharts
```

### Example Configurations

**Gateway API (Recommended):**
```yaml
routing:
  type: "gateway"

gateway:
  enabled: true
  create: true
  gatewayClassName: "istio"
  
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      allowedRoutes:
        namespaces:
          from: Same
    - name: https
      protocol: HTTPS
      port: 443
      allowedRoutes:
        namespaces:
          from: Same
      tls:
        mode: Terminate
        certificateRefs:
          - name: gharts-tls
  
  httpRoute:
    hostnames:
      - "gharts.example.com"
    tlsRedirect: true
```

**Ingress (Legacy):**
```yaml
routing:
  type: "ingress"

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: gharts.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: gharts-tls
      hosts:
        - gharts.example.com
```

### Gateway API Implementations

**Supported Gateway Controllers:**
- **Istio**: Full-featured service mesh with Gateway API support
- **Nginx Gateway Fabric**: Nginx-based implementation
- **Contour**: Envoy-based ingress controller
- **Traefik**: Modern HTTP reverse proxy
- **Kong**: API gateway with Gateway API support
- **AWS Load Balancer Controller**: Native AWS integration
- **GKE Gateway**: Google Cloud native implementation

**Installation Examples:**

**Istio:**
```bash
helm repo add istio https://istio-release.storage.googleapis.com/charts
helm install istio-base istio/base -n istio-system --create-namespace
helm install istiod istio/istiod -n istio-system
helm install istio-gateway istio/gateway -n istio-system
```

**Nginx Gateway Fabric:**
```bash
helm repo add nginx-stable https://helm.nginx.com/stable
helm install nginx-gateway nginx-stable/nginx-gateway --create-namespace -n nginx-gateway
```

        - path: /
          pathType: Prefix
  tls:
    - secretName: gharts-tls
      hosts:
        - gharts.example.com
```

3. **Create secrets:**
```bash
# GitHub App private key
kubectl create secret generic github-app-key \
  --from-file=private-key.pem=./github-app-private-key.pem

# Database credentials (if not using values file)
kubectl create secret generic gharts-db \
  --from-literal=url="postgresql://..."
```

4. **Install:**
```bash
helm install gharts gharts/gharts \
  -f values-prod.yaml \
  --namespace gharts \
  --create-namespace
```

5. **Get bootstrap admin password:**
```bash
kubectl get secret gharts-bootstrap-admin \
  -n gharts \
  -o jsonpath='{.data.admin-password}' | base64 -d
```

### AWS-Specific Configuration

**RDS PostgreSQL:**
```yaml
database:
  url: "postgresql://gharts:PASSWORD@gharts-db.abc123.us-east-1.rds.amazonaws.com:5432/gharts?sslmode=require"
  sslMode: "require"
  poolSize: 20
  maxOverflow: 40
```

**Aurora DSQL:**
```yaml
database:
  url: "postgresql://gharts:PASSWORD@gharts-cluster.cluster-abc123.us-east-1.rds.amazonaws.com:5432/gharts?sslmode=require"
  sslMode: "verify-full"
  sslCA:
    enabled: true
    secretName: "rds-ca-cert"
    secretKey: "ca.crt"
```

**IAM Authentication** (future enhancement):
```yaml
database:
  url: "postgresql://gharts@gharts-db.abc123.us-east-1.rds.amazonaws.com:5432/gharts"
  iamAuth: true

serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/gharts-db-access
```

## AI-Proposed Enhancements

### 1. Multi-Region Deployment

**Problem**: Single region deployment creates availability risk.

**Solution**:
- Active-active deployment across regions
- Global load balancer (AWS Global Accelerator)
- Database replication (Aurora Global Database)
- Regional failover automation

**Implementation**:
```yaml
# values-multi-region.yaml
global:
  region: us-east-1
  
database:
  replication:
    enabled: true
    readReplicas:
      - region: us-west-2
        endpoint: "replica.us-west-2.rds.amazonaws.com"
      - region: eu-west-1
        endpoint: "replica.eu-west-1.rds.amazonaws.com"
```

### 2. Observability Stack

**Problem**: Limited visibility into production operations.

**Solution**:
- Prometheus metrics export
- Grafana dashboards
- Distributed tracing (OpenTelemetry)
- Log aggregation (ELK/Loki)

**Metrics to Export**:
- Runner provisioning rate
- Token generation latency
- Database connection pool stats
- OIDC authentication success/failure
- API endpoint latency (p50, p95, p99)
- GitHub API rate limit usage

**Implementation**:
```python
# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge

runner_provisions = Counter(
    'gharts_runner_provisions_total',
    'Total runner provisions',
    ['status', 'user']
)

token_generation_duration = Histogram(
    'gharts_token_generation_seconds',
    'Token generation duration'
)

active_runners = Gauge(
    'gharts_active_runners',
    'Number of active runners'
)
```

### 3. Secrets Management Integration

**Problem**: Secrets in Kubernetes Secrets are base64-encoded, not encrypted at rest.

**Solution**:
- AWS Secrets Manager integration
- HashiCorp Vault integration
- External Secrets Operator

**Implementation**:
```yaml
# Using External Secrets Operator
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: gharts-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: gharts-secrets
  data:
    - secretKey: database-url
      remoteRef:
        key: gharts/database-url
    - secretKey: github-private-key
      remoteRef:
        key: gharts/github-private-key
```

### 4. Backup and Disaster Recovery

**Problem**: No automated backup strategy.

**Solution**:
- Automated database backups
- Point-in-time recovery
- Backup verification
- Disaster recovery runbooks

**Implementation**:
```yaml
# Velero backup configuration
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: gharts-daily-backup
spec:
  schedule: "0 2 * * *"
  template:
    includedNamespaces:
      - gharts
    storageLocation: aws-s3
    volumeSnapshotLocations:
      - aws-ebs
```

### 5. Rate Limiting and DDoS Protection

**Problem**: No protection against abuse or DDoS attacks.

**Solution**:
- Rate limiting per user/IP
- Request throttling
- WAF integration (AWS WAF)
- Circuit breaker pattern

**Implementation**:
```python
# app/middleware/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/runners/provision")
@limiter.limit("10/minute")
async def provision_runner(...):
    ...
```

### 6. Cost Optimization

**Problem**: Running costs can be high with always-on infrastructure.

**Solution**:
- Spot instances for non-critical workloads
- Cluster autoscaling
- Database connection pooling optimization
- Scheduled scaling (scale down during off-hours)

**Implementation**:
```yaml
# Karpenter node provisioner for spot instances
apiVersion: karpenter.sh/v1alpha5
kind: Provisioner
metadata:
  name: gharts-spot
spec:
  requirements:
    - key: karpenter.sh/capacity-type
      operator: In
      values: ["spot"]
  limits:
    resources:
      cpu: 100
```

### 7. Compliance and Audit

**Problem**: Limited audit trail for compliance requirements.

**Solution**:
- Comprehensive audit logging
- Immutable audit log storage
- Compliance reporting
- GDPR/SOC2 compliance features

**Features**:
- All admin actions logged
- User data export API
- Data retention policies
- Audit log encryption

### 8. GitOps Deployment

**Problem**: Manual Helm deployments are error-prone.

**Solution**:
- ArgoCD/Flux for GitOps
- Automated deployment from Git
- Rollback capabilities
- Progressive delivery

**Implementation**:
```yaml
# ArgoCD Application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: gharts
spec:
  project: default
  source:
    repoURL: https://github.com/[org]/gha-runner-token-service
    targetRevision: main
    path: charts/gharts
    helm:
      valueFiles:
        - values-production.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: gharts
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 9. Development Environment

**Problem**: Difficult to test Kubernetes deployments locally.

**Solution**:
- Kind/Minikube local cluster
- Skaffold for development
- Tilt for live reload
- Docker Compose alternative

**Implementation**:
```yaml
# skaffold.yaml
apiVersion: skaffold/v4beta1
kind: Config
build:
  artifacts:
    - image: gharts-backend
      docker:
        dockerfile: Dockerfile.backend
deploy:
  helm:
    releases:
      - name: gharts
        chartPath: charts/gharts
        valuesFiles:
          - charts/gharts/values-dev.yaml
```

### 10. Performance Testing

**Problem**: Unknown performance characteristics under load.

**Solution**:
- Load testing framework (k6, Locust)
- Performance benchmarks
- Capacity planning
- Automated performance regression tests

**Implementation**:
```javascript
// k6 load test
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 100 },
    { duration: '2m', target: 0 },
  ],
};

export default function() {
  let res = http.post('https://gharts.example.com/api/v1/runners/provision', {
    headers: { 'Authorization': 'Bearer ${TOKEN}' },
  });
  check(res, { 'status is 200': (r) => r.status === 200 });
}
```

## Migration Path

### From Current Setup to Kubernetes

1. **Phase 1: Preparation**
   - Remove legacy dashboard
   - Update configuration for cloud database
   - Test Docker builds locally
   - Create Helm chart

2. **Phase 2: Staging Deployment**
   - Deploy to staging Kubernetes cluster
   - Test bootstrap admin flow
   - Verify OIDC integration
   - Load test

3. **Phase 3: Production Deployment**
   - Deploy to production cluster
   - Migrate database (if needed)
   - Update DNS/ingress
   - Monitor and validate

4. **Phase 4: Optimization**
   - Enable autoscaling
   - Configure monitoring
   - Implement backup strategy
   - Document runbooks

## Security Considerations

1. **Network Security**
   - Network policies to restrict pod communication
   - TLS for all external communication
   - Private subnets for database

2. **Secret Management**
   - Secrets encrypted at rest
   - Rotation policies
   - Least privilege access

3. **Container Security**
   - Non-root user
   - Read-only root filesystem
   - Security scanning (Trivy, Snyk)
   - Minimal base images

4. **Access Control**
   - RBAC for Kubernetes resources
   - Service accounts with minimal permissions
   - Pod security standards

## Monitoring and Alerting

**Key Metrics to Monitor:**
- Pod health and restarts
- Database connection pool utilization
- API response times
- Error rates
- GitHub API rate limit
- OIDC authentication failures

**Alerts to Configure:**
- Pod crash loops
- High error rate (>5%)
- Database connection failures
- GitHub API rate limit approaching
- Certificate expiration

## Conclusion

This design provides a comprehensive path to deploying GHARTS on Kubernetes with:
- Production-ready container images
- Flexible Helm chart configuration
- Automated CI/CD pipelines
- Security best practices
- Scalability and high availability
- Cloud-native architecture

The bootstrap admin mechanism provides a secure way to initialize the system while maintaining security through auto-disable after OIDC admin setup.