FROM node:22-slim AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile
COPY . .
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
RUN NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE} pnpm run build
# Remove auto-generated proxy middleware that hard-codes NEXT_PUBLIC_API_BASE at build time.
# Without this, Next.js intercepts /api/* before our route.ts handler can run.
RUN node -e "const fs=require('fs'); \
    ['.next/server/functions-config-manifest.json', \
     '.next/standalone/.next/server/functions-config-manifest.json'].forEach(p => { \
      if (!fs.existsSync(p)) return; \
      const m=JSON.parse(fs.readFileSync(p,'utf8')); \
      delete m.functions['/_middleware']; \
      fs.writeFileSync(p,JSON.stringify(m,null,2)); \
      console.log('Patched', p); \
    });"

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
