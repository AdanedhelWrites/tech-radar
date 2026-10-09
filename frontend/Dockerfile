# ============================================
# Frontend Dockerfile — Production Ready
# Multi-stage: Node build + Nginx serve
# ============================================

# --- Stage 1: Build ---
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS builder

RUN apk upgrade --no-cache

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .

# Build-time API URL (nginx proxy'leyecegi icin /api yeterli)
ENV VITE_API_URL=/api
RUN npm run build

# --- Stage 2: Serve ---
FROM nginx:1.31-alpine@sha256:df221db836e1754089190208cee7eeda94f233197056426eda74a43ab1abeac2

RUN apk upgrade --no-cache

# Custom nginx config + SPA guvenlik basliklari snippet'i (2026-10-08)
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY guvenlik_basliklari.conf /etc/nginx/snippets/guvenlik_basliklari.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Non-root user (nginx alpine bunu destekler)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

EXPOSE 3000

USER nginx

CMD ["nginx", "-g", "daemon off;"]
