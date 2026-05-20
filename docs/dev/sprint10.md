# Sprint 10 — Continuous Deployment

## Goal

Close the CI/CD loop. Every merge to `main` should automatically build and push the Docker
image to Azure Container Registry, update the persistent `clipsmith-api` ACI instance
running the FastAPI server, and verify the deployment with a `/health` gate before marking
the workflow successful. A failed health check re-deploys the previous image SHA so no bad
deploy stays live.

After this sprint the project demonstrates the full engineering lifecycle: code → review →
CI → build → push → deploy → verify.

---

## Step 0 — Doc Pre-flight

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 10 status | `🔜 Planned` → `🚧 In Progress` |

---

## Step 1 — GitHub Actions Secrets

Before writing the workflow, add these secrets to the GitHub repository
(Settings → Secrets and variables → Actions):

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | Service principal client ID (from Sprint 6 SP) |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `ACR_LOGIN_SERVER` | ACR login server URL (from `terraform output`) |
| `ACR_USERNAME` | ACR admin username |
| `ACR_PASSWORD` | ACR admin password |
| `RESOURCE_GROUP` | `clipsmith-rg-dev` (or prod) |
| `ACI_NAME_DEV` | `clipsmith-api-dev` |
| `ACI_NAME_PROD` | `clipsmith-api-prod` |
| `CLIPSMITH_API_KEY` | The `CLIPSMITH_API_KEY` to inject into the container |

Use OIDC federated credentials instead of a long-lived client secret where possible:

```bash
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{"name":"github-deploy","issuer":"https://token.actions.githubusercontent.com","subject":"repo:ricardogr07/clipsmith:ref:refs/heads/main","audiences":["api://AzureADTokenExchange"]}'
```

---

## Step 2 — Persistent ACI Instance

Unlike the ephemeral pipeline ACI created by `clipsmith cloud run`, the API server is a
*persistent* container that runs continuously. Provision it once (or via Terraform) and
the deploy workflow updates it in place.

### Bootstrap (one-time, run manually or add to Terraform)

```bash
# Create the dev API container (run once)
az container create \
  --resource-group clipsmith-rg-dev \
  --name clipsmith-api-dev \
  --image "$ACR_LOGIN_SERVER/clipsmith:latest" \
  --registry-login-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --cpu 1 \
  --memory 2 \
  --ports 8000 \
  --ip-address Public \
  --environment-variables \
    CLIPSMITH_API_KEY="$CLIPSMITH_API_KEY" \
    DATABASE_URL="sqlite:////app/data/clipsmith.db" \
  --azure-file-volume-account-name "$STORAGE_ACCOUNT" \
  --azure-file-volume-account-key "$STORAGE_KEY" \
  --azure-file-volume-share-name clipsmith-work \
  --azure-file-volume-mount-path /app/data
```

Add the bootstrap command to `docs/cloud.md` under a "Persistent API server" section.

---

## Step 3 — `deploy.yml` Workflow

### `.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment (dev | prod)
        default: dev
        type: choice
        options: [dev, prod]

permissions:
  id-token: write   # required for OIDC
  contents: read

env:
  IMAGE_NAME: clipsmith

jobs:
  # ── 1. Build and push image to ACR ────────────────────────────────────────
  build:
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.meta.outputs.version }}
    steps:
      - uses: actions/checkout@v4

      - name: Azure login (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Log in to ACR
        run: |
          az acr login --name ${{ secrets.ACR_LOGIN_SERVER }}

      - name: Image metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=sha-,format=short
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=registry,ref=${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:latest
          cache-to: type=inline

  # ── 2. Deploy to dev ──────────────────────────────────────────────────────
  deploy-dev:
    needs: build
    runs-on: ubuntu-latest
    environment: dev
    env:
      ACI_NAME: ${{ secrets.ACI_NAME_DEV }}
    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Update container image
        run: |
          IMAGE="${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:sha-${{ github.sha }}"
          az container create \
            --resource-group ${{ secrets.RESOURCE_GROUP }} \
            --name "$ACI_NAME" \
            --image "$IMAGE" \
            --registry-login-server "${{ secrets.ACR_LOGIN_SERVER }}" \
            --registry-username "${{ secrets.ACR_USERNAME }}" \
            --registry-password "${{ secrets.ACR_PASSWORD }}" \
            --cpu 1 --memory 2 \
            --ports 8000 \
            --ip-address Public \
            --restart-policy Always \
            --environment-variables \
              CLIPSMITH_API_KEY="${{ secrets.CLIPSMITH_API_KEY }}" \
              DATABASE_URL="sqlite:////app/data/clipsmith.db" \
            --no-wait

      - name: Wait for container to start
        run: |
          for i in $(seq 1 12); do
            STATE=$(az container show \
              --resource-group ${{ secrets.RESOURCE_GROUP }} \
              --name "$ACI_NAME" \
              --query "instanceView.state" -o tsv 2>/dev/null || echo "Unknown")
            echo "State: $STATE (attempt $i/12)"
            [ "$STATE" = "Running" ] && break
            sleep 10
          done

      - name: Get container IP
        id: ip
        run: |
          IP=$(az container show \
            --resource-group ${{ secrets.RESOURCE_GROUP }} \
            --name "$ACI_NAME" \
            --query "ipAddress.ip" -o tsv)
          echo "ip=$IP" >> "$GITHUB_OUTPUT"

      - name: Health check
        id: health
        run: |
          URL="http://${{ steps.ip.outputs.ip }}:8000/health"
          for i in $(seq 1 6); do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL" || echo "000")
            echo "Health: $STATUS (attempt $i/6)"
            [ "$STATUS" = "200" ] && exit 0
            sleep 10
          done
          echo "::error::Health check failed after 60s"
          exit 1

      - name: Rollback on failure
        if: failure() && steps.health.outcome == 'failure'
        run: |
          PREV_IMAGE="${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:latest"
          echo "Rolling back to $PREV_IMAGE"
          az container create \
            --resource-group ${{ secrets.RESOURCE_GROUP }} \
            --name "$ACI_NAME" \
            --image "$PREV_IMAGE" \
            --registry-login-server "${{ secrets.ACR_LOGIN_SERVER }}" \
            --registry-username "${{ secrets.ACR_USERNAME }}" \
            --registry-password "${{ secrets.ACR_PASSWORD }}" \
            --cpu 1 --memory 2 \
            --ports 8000 \
            --ip-address Public \
            --restart-policy Always \
            --environment-variables \
              CLIPSMITH_API_KEY="${{ secrets.CLIPSMITH_API_KEY }}" \
              DATABASE_URL="sqlite:////app/data/clipsmith.db"

  # ── 3. Promote to prod (manual gate) ──────────────────────────────────────
  deploy-prod:
    needs: deploy-dev
    runs-on: ubuntu-latest
    environment: prod          # GitHub environment with required reviewers set
    if: github.event_name == 'workflow_dispatch' && github.event.inputs.environment == 'prod'
    env:
      ACI_NAME: ${{ secrets.ACI_NAME_PROD }}
    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Deploy to prod
        run: |
          IMAGE="${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:sha-${{ github.sha }}"
          az container create \
            --resource-group ${{ secrets.RESOURCE_GROUP }} \
            --name "$ACI_NAME" \
            --image "$IMAGE" \
            --registry-login-server "${{ secrets.ACR_LOGIN_SERVER }}" \
            --registry-username "${{ secrets.ACR_USERNAME }}" \
            --registry-password "${{ secrets.ACR_PASSWORD }}" \
            --cpu 2 --memory 4 \
            --ports 8000 \
            --ip-address Public \
            --restart-policy Always \
            --environment-variables \
              CLIPSMITH_API_KEY="${{ secrets.CLIPSMITH_API_KEY }}" \
              DATABASE_URL="${{ secrets.DATABASE_URL_PROD }}"

      - name: Prod health check
        run: |
          IP=$(az container show \
            --resource-group ${{ secrets.RESOURCE_GROUP }} \
            --name "$ACI_NAME" \
            --query "ipAddress.ip" -o tsv)
          curl --retry 6 --retry-delay 10 --retry-connrefused -sf "http://$IP:8000/health"
```

---

## Step 4 — Dockerfile Hardening

The existing `Dockerfile` works but should be validated for the persistent-server use case.

### Key additions

```dockerfile
# Use a specific digest for reproducibility
FROM python:3.11-slim@sha256:<digest>

# Non-root user
RUN groupadd -r clipsmith && useradd -r -g clipsmith clipsmith

# Install server extras
RUN pip install --no-cache-dir -e ".[server,observability]"

# Run as non-root
USER clipsmith

# Health check so ACI reports container health
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "clipsmith.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Step 5 — Alembic in the Container

The API server must run `alembic upgrade head` on startup before accepting requests.
Add a startup script:

### `scripts/start_server.sh`

```bash
#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting clipsmith API..."
exec uvicorn clipsmith.api.app:app --host 0.0.0.0 --port 8000 "$@"
```

### `Dockerfile`

```dockerfile
COPY scripts/start_server.sh /app/start_server.sh
RUN chmod +x /app/start_server.sh
CMD ["/app/start_server.sh"]
```

---

## Step 6 — GitHub Environment Configuration

In GitHub → Settings → Environments:

**dev environment:**
- No required reviewers (auto-deploys on every merge to `main`)
- Deployment branch rule: `main` only

**prod environment:**
- Required reviewers: (your own account)
- Deployment branch rule: `main` only
- All secrets specific to prod (separate ACI name, DATABASE_URL, etc.)

---

## File Layout (final state after Sprint 10)

```
.github/workflows/
├── ci.yml          UNCHANGED (still tests on every push/PR)
└── deploy.yml      NEW — build → push → deploy-dev → (manual) deploy-prod

scripts/
└── start_server.sh NEW — alembic upgrade head + uvicorn

Dockerfile          MODIFIED — non-root user, HEALTHCHECK, start_server.sh entrypoint
```

---

## Verification Checklist

### Build job
- [ ] Merge to `main` triggers `deploy.yml`
- [ ] Docker image builds successfully and is pushed to ACR
- [ ] Both `sha-<short-sha>` and `latest` tags appear in ACR
- [ ] Layer cache hits reduce build time on subsequent merges

### Deploy to dev
- [ ] ACI container is updated with the new image SHA
- [ ] Container reaches `Running` state within 2 minutes
- [ ] `GET http://<aci-ip>:8000/health` returns `{"status": "ok"}`
- [ ] Workflow step `Health check` goes green

### Rollback
- [ ] Temporarily break the health endpoint → health check fails → rollback job runs
- [ ] After rollback, `GET /health` returns 200 with the previous image

### Prod promotion
- [ ] `workflow_dispatch` with `environment=prod` triggers `deploy-prod`
- [ ] GitHub pauses for required reviewer approval at the `prod` environment gate
- [ ] After approval, prod ACI is updated
- [ ] Prod health check passes

### Alembic on startup
- [ ] Container logs show "Running database migrations..." before uvicorn starts
- [ ] `alembic upgrade head` succeeds even when the DB already has all migrations applied (idempotent)
- [ ] A schema drift (model change without migration) causes `alembic upgrade head` to fail fast, preventing a bad deploy from accepting traffic

### Security
- [ ] No secrets appear in workflow logs (CLIPSMITH_API_KEY, ACR_PASSWORD masked)
- [ ] OIDC login is used — no long-lived client secrets stored in GitHub
- [ ] Container runs as non-root (`clipsmith` user)
