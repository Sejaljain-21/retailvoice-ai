# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# RetailVoice AI - frontend image (build with Node, serve with nginx)
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Relative API base keeps the browser on one origin; nginx proxies to the API.
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
