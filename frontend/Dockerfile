# ============================================
# Frontend Dockerfile — Production Ready
# Multi-stage: Node build + Nginx serve
# ============================================

# --- Stage 1: Build ---
FROM node:22-alpine@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85 AS builder

RUN apk upgrade --no-cache

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .

# Build-time API URL (nginx proxy'leyecegi icin /api yeterli)
ENV VITE_API_URL=/api
RUN npm run build

# --- Stage 2: Serve ---
FROM nginx:1.31-alpine@sha256:62ff2089abf5a9ed33bd232895bef5e22f7bb4b200675cec49a5ebc48e3d4ac8

RUN apk upgrade --no-cache

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

USER nginx

CMD ["nginx", "-g", "daemon off;"]
