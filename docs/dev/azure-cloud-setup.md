# Azure Cloud Setup

This covers every manual step required before `clipsmith cloud` commands work.
Go through each section in order. Once complete, fill in `.env` and run `clipsmith cloud setup` to verify.

---

## 1. Prerequisites

| Tool | Version | Install |
|---|---|---|
| Azure CLI | ≥ 2.58 | https://learn.microsoft.com/en-us/cli/azure/install-azure-cli |
| Docker Desktop | ≥ 25 | https://www.docker.com/products/docker-desktop/ |
| Python | 3.11+ | already in your clipsmith env |

```powershell
az --version
docker --version
```

---

## 2. Azure Account & Subscription

1. Log in at https://portal.azure.com (create a free account if needed — 12 months free + $200 credit)
2. Note your **Subscription ID**: Portal → Subscriptions → copy the ID

```powershell
az login
az account show   # confirm the right subscription is active

# If you have multiple subscriptions:
az account set --subscription "<your-subscription-id>"
```

Add to `.env`:
```env
AZURE_SUBSCRIPTION_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

> **Storage is automatic.** `clipsmith cloud run` provisions a fresh resource group,
> storage account, and file shares on every run, then deletes them all on completion.
> No manual storage setup is needed.

---

## 3. ACI Provider Registration

Only needed the first time you use ACI on this subscription:

```powershell
az provider register --namespace Microsoft.ContainerInstance
az provider show --namespace Microsoft.ContainerInstance --query "registrationState"
# Wait until output is "Registered" (usually < 2 min)
```

---

## 4. GPU Quota (Optional — skip for CPU-only)

CPU (`int8` Whisper small/medium) costs ~$0.28/run for a 2-hr VOD.
GPU (V100) is ~10× faster but ~$1.80/run — worthwhile only if you process many long VODs per day.

To request GPU quota:

1. Portal → Subscriptions → `<your-sub>` → Usage + quotas
2. Filter by "Container Instances" → "Standard NV Family vCPUs"
3. Click **Request increase** → set to at least 4 cores → submit

Available GPU SKUs for ACI (set in `config.yaml` as `cloud.gpu_sku`):

| SKU | VRAM | Cost/hr | Speed vs CPU |
|---|---|---|---|
| K80 | 12 GB | ~$0.90 | ~3× |
| P100 | 16 GB | ~$1.25 | ~5× |
| V100 | 16 GB | ~$1.80 | ~10× |

> GPU ACI is only available in `eastus`, `westus`, `southcentralus`, `northeurope`, `westeurope`.

---

## 5. Docker Hub

1. Create an account at https://hub.docker.com
2. Create a repository: `hub.docker.com/r/<youruser>/clipsmith`
3. Create a **read-only Access Token**: Account Settings → Security → New Access Token
4. Log in locally: `docker login -u <yourdockerhubuser>`

The access token (not your password) goes in `.env`. A read-only token limits exposure if the credential is ever leaked, and is sufficient — ACI only needs to pull, not push.

```env
DOCKER_HUB_USERNAME=<yourdockerhubuser>
DOCKER_HUB_PASSWORD=<read-only-access-token>
```

Update `config.yaml`:
```yaml
cloud:
  docker_image: "<yourdockerhubuser>/clipsmith:latest"
```

> **Why this is necessary**: Azure IPs share an anonymous Docker Hub pull rate limit of 100 pulls / 6 hours. Without authentication, ACI container creation fails with a 409 error when that limit is hit.

---

## 6. Google Drive — OAuth2 Setup

clipsmith uses **OAuth2 user credentials** (not a service account) because Google service accounts have no storage quota on personal Google Drive — any file they upload causes a `storageQuotaExceeded` error. OAuth2 files are owned by your real Google account and count against your 15 GB quota.

### 6a. Create a Google Cloud project

1. Go to https://console.cloud.google.com/
2. Click the project dropdown → **New Project** → name: `clipsmith` → **Create**

### 6b. Enable the Drive API

1. Navigation menu → **APIs & Services** → **Library**
2. Search "Google Drive API" → **Enable**

### 6c. Configure the OAuth consent screen

1. **APIs & Services** → **OAuth consent screen**
2. User type: **External** → **Create**
3. Fill in app name (`clip-smith`), support email, developer email → **Save and continue**
4. Scopes: skip → **Save and continue**
5. Test users: add your Gmail address → **Save and continue**

> You must add yourself as a test user while the app is in "Testing" status. Without this, the OAuth flow will show "Access blocked: clip-smith has not completed the Google verification process".

### 6d. Create an OAuth2 Desktop app client

1. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
2. Application type: **Desktop app** → name: `clipsmith-local` → **Create**
3. Click **Download JSON** → save as `google_oauth_client.json` in your clipsmith directory

`google_oauth_client.json` is already covered by `.gitignore`. Do not commit it.

### 6e. Create your Drive folder

1. Open Google Drive → create a folder (e.g. `chuyelwero`)
2. Note the **folder ID** from the URL: `https://drive.google.com/drive/folders/<FOLDER_ID>`

Add to `.env`:
```env
GOOGLE_OAUTH_CLIENT_JSON=C:\git\clipsmith\google_oauth_client.json
GOOGLE_DRIVE_FOLDER_ID=<folder-id-from-url>
```

### 6f. Authorize (one-time browser login)

```powershell
clipsmith cloud drive-auth
```

This opens a browser. Log in with your Google account → grant access → the token is saved to `~/.clipsmith_drive_token.json`. You will not need to repeat this unless the token is deleted.

---

## 7. `config.yaml` Cloud Section

```yaml
cloud:
  location: eastus
  aci_cpu: 4.0
  aci_memory_gb: 16.0
  docker_image: "<yourdockerhubuser>/clipsmith:latest"
  gpu_sku: ""           # uncomment and set to V100 etc. for GPU (requires Step 4)
```

The `resource_group` and `storage_account` fields are no longer required — resources are
provisioned automatically per run and torn down on completion.

---

## 8. Build and Verify

```powershell
# Build the Docker image and push to Docker Hub
# First build is ~10 min (Whisper model gets baked in)
clipsmith cloud build

# Verify Azure credentials are valid
clipsmith cloud setup

# Dry-run: print the ACI spec without provisioning anything
clipsmith cloud run <vod_id> --game "Game Name" --dry-run

# Full run
clipsmith cloud run <vod_id> --game "Game Name" --date 2026-05-03
```

---

## Cost Reference

| Resource | When charged | Cost |
|---|---|---|
| ACI CPU (4 vCPU / 16 GB) | Per second of container runtime | ~$0.28 for 60-min run |
| ACI GPU V100 | Per second of container runtime | ~$1.80 for 60-min run |
| Azure File Share (Standard) | Per GB provisioned per month | < $0.01 (deleted after run) |
| Docker Hub | Free public repo | $0 |
| Google Drive | Free up to 15 GB | $0 |

**Typical total per 2-hr VOD (CPU): ~$0.30.**

Storage costs are negligible because `clipsmith cloud run` deletes both file share directories immediately after downloading the clips.
