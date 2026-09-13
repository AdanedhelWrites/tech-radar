# ============================================
# Frontend Dockerfile — Production Ready
# Multi-stage: Node build + Nginx serve
# ============================================

# --- Stage 1: Build ---
FROM node:26-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .

# Build-time API URL (nginx proxy'leyecegi icin /api yeterli)
ENV VITE_API_URL=/api
RUN npm run build

# --- Stage 2: Serve ---
FROM nginx:1.25-alpine

# Custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Non-root user (nginx alpine bunu destekler)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
