# The front end image: the Next.js app built once and served by its own small Node server on 3000.
# Build context is web/ (docker-compose.yml builds it).  /api/* is proxied to the API by the rewrite in
# next.config.ts; the address is fixed at build time, so pass it as a build argument (default: the `api`
# service of docker-compose.yml; on a platform, the API service's URL).
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
ARG API_URL=http://api:8000
ENV API_URL=$API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S app && adduser -S app -G app
# `output: "standalone"` in next.config.ts: the server and only the modules it needs
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
USER app
EXPOSE 3000
CMD ["node", "server.js"]
