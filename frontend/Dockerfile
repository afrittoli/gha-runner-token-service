# Multi-stage build for GHARTS frontend
# Stage 1: Builder - Build React application with NO environment-specific config
FROM node:20-alpine AS builder

WORKDIR /build

# Copy package files
COPY package*.json ./

# Install all dependencies (including devDependencies needed for build)
RUN npm ci

# Copy source code
COPY . .

# Build the application (generic build, no environment variables)
RUN npm run build

# Stage 2: Runtime - Nginx server with runtime configuration injection
FROM nginx:alpine AS runtime

# Install gettext for envsubst command
RUN apk add --no-cache gettext

# Create non-root user for Nginx
RUN addgroup -g 1000 -S appuser && \
    adduser -u 1000 -S appuser -G appuser

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Copy runtime config template to a location that won't be overwritten
COPY public/config.template.js /etc/nginx/config.template.js

# Copy built assets from builder
COPY --from=builder /build/dist /usr/share/nginx/html

# Create necessary directories and set permissions
# Make /usr/share/nginx/html writable so entrypoint can create config.js
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx && \
    chown -R appuser:appuser /var/cache/nginx /var/run /var/log/nginx /usr/share/nginx/html && \
    chmod -R 755 /var/cache/nginx /var/run /var/log/nginx && \
    chmod 775 /usr/share/nginx/html

# Create health check endpoint
RUN echo '<!DOCTYPE html><html><body>OK</body></html>' > /usr/share/nginx/html/health

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Set entrypoint to generate runtime config, then start Nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]