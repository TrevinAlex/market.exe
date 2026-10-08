# ---- build the SPA ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# VITE_API_BASE left empty: the SPA calls /api on its own origin (Caddy proxies it)
RUN npm run build

# ---- serve with Caddy (auto HTTPS + reverse proxy to backend) ----
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
