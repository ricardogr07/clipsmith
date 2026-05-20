# Sprint 6 — Infrastructure as Code

## Goal

Replace the ad-hoc Azure provisioning scripts with reproducible Terraform modules. Move all
secrets from plain environment variables to Azure Key Vault. Swap Docker Hub for Azure Container
Registry so images are private, co-located with ACI, and free of rate-limit surprises. Add
Terraform validation to the CI lint job so infrastructure drift is caught on every PR.

The `infra/` directory currently contains a single JSON file. After this sprint it is a
complete, environment-parameterised Terraform workspace.

---

## Step 0 — Doc Pre-flight

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 6 status | `🔜 Planned` → `🚧 In Progress` |

---

## Step 1 — Terraform Module Structure

### Directory layout

```
infra/
├── main.tf              Root module: calls child modules, wires outputs
├── variables.tf         All input variables with descriptions and defaults
├── outputs.tf           Exported values (ACR login server, Key Vault URI, etc.)
├── versions.tf          Required providers and version constraints
├── terraform.tfvars     Local overrides (gitignored — never committed)
├── modules/
│   ├── storage/         Azure Storage Account + two File Shares (work, out)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── registry/        Azure Container Registry (Basic SKU)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── keyvault/        Azure Key Vault + access policy for the ACI service principal
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── network/         (optional) Virtual network for private ACI networking
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── environments/
    ├── dev.tfvars       Dev-environment variable overrides
    └── prod.tfvars      Prod-environment variable overrides
```

### `infra/versions.tf`

```hcl
terraform {
  required_version = ">= 1.7"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.47"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
}
```

### `infra/variables.tf`

```hcl
variable "resource_group_name" {
  description = "Name of the Azure resource group"
  type        = string
  default     = "clipsmith-rg"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Deployment environment (dev | prod)"
  type        = string
  default     = "dev"
}

variable "aci_sp_object_id" {
  description = "Object ID of the ACI service principal that reads Key Vault secrets"
  type        = string
}

variable "secrets" {
  description = "Map of secret name → value to store in Key Vault"
  type        = map(string)
  sensitive   = true
  default     = {}
}
```

### `infra/main.tf`

```hcl
resource "azurerm_resource_group" "main" {
  name     = "${var.resource_group_name}-${var.environment}"
  location = var.location
}

module "storage" {
  source              = "./modules/storage"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
}

module "registry" {
  source              = "./modules/registry"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
}

module "keyvault" {
  source              = "./modules/keyvault"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  aci_sp_object_id    = var.aci_sp_object_id
  secrets             = var.secrets
}
```

---

## Step 2 — Storage Module

### `infra/modules/storage/main.tf`

```hcl
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_storage_account" "main" {
  name                     = "clipsmith${var.environment}${random_string.suffix.result}"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_share" "work" {
  name                 = "clipsmith-work"
  storage_account_name = azurerm_storage_account.main.name
  quota                = 100  # GB
}

resource "azurerm_storage_share" "out" {
  name                 = "clipsmith-out"
  storage_account_name = azurerm_storage_account.main.name
  quota                = 50
}
```

### `infra/modules/storage/outputs.tf`

```hcl
output "account_name"  { value = azurerm_storage_account.main.name }
output "account_key"   { value = azurerm_storage_account.main.primary_access_key; sensitive = true }
output "work_share"    { value = azurerm_storage_share.work.name }
output "out_share"     { value = azurerm_storage_share.out.name }
```

---

## Step 3 — Registry Module (ACR)

### `infra/modules/registry/main.tf`

```hcl
resource "azurerm_container_registry" "main" {
  name                = "clipsmith${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = true
}
```

### `infra/modules/registry/outputs.tf`

```hcl
output "login_server"    { value = azurerm_container_registry.main.login_server }
output "admin_username"  { value = azurerm_container_registry.main.admin_username }
output "admin_password"  { value = azurerm_container_registry.main.admin_password; sensitive = true }
```

---

## Step 4 — Key Vault Module

### `infra/modules/keyvault/main.tf`

```hcl
data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                = "clipsmith-${var.environment}-kv"
  resource_group_name = var.resource_group_name
  location            = var.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Terraform itself gets full access
  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id
    secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
  }

  # ACI service principal gets read-only access
  access_policy {
    tenant_id          = data.azurerm_client_config.current.tenant_id
    object_id          = var.aci_sp_object_id
    secret_permissions = ["Get", "List"]
  }
}

resource "azurerm_key_vault_secret" "secrets" {
  for_each     = var.secrets
  name         = replace(each.key, "_", "-")   # Key Vault names can't have underscores
  value        = each.value
  key_vault_id = azurerm_key_vault.main.id
}
```

### `infra/modules/keyvault/outputs.tf`

```hcl
output "vault_uri" { value = azurerm_key_vault.main.vault_uri }
output "vault_id"  { value = azurerm_key_vault.main.id }
```

---

## Step 5 — Key Vault Integration in `azure_runner.py`

At container-create time, resolve secret values from Key Vault instead of reading them
from local environment variables.

### `src/clipsmith/cloud/azure_runner.py`

Add a `_resolve_secrets` helper that uses `azure-keyvault-secrets` (already available
through `azure-identity`):

```python
def _resolve_secrets(vault_uri: str, secret_names: list[str]) -> dict[str, str]:
    """Fetch named secrets from Azure Key Vault at ACI provision time."""
    from azure.keyvault.secrets import SecretClient
    from azure.identity import DefaultAzureCredential

    client = SecretClient(vault_url=vault_uri, credential=DefaultAzureCredential())
    return {
        name: client.get_secret(name.replace("_", "-")).value or ""
        for name in secret_names
    }
```

Call `_resolve_secrets` before `ContainerGroup` creation when `cloud.key_vault_uri`
is set in config, and pass the resolved values as ACI environment variables instead
of local env vars.

### `src/clipsmith/config/models.py`

```python
class CloudConfig(BaseModel):
    location: str = "eastus"
    aci_cpu: float = 4.0
    aci_memory_gb: float = 16.0
    docker_image: str = "ricardogr07/clipsmith:latest"
    acr_login_server: str = ""           # NEW: set to ACR login server when using ACR
    acr_username: str = ""               # NEW
    acr_password: str = ""               # NEW (loaded from Key Vault or env)
    key_vault_uri: str = ""              # NEW: if set, secrets resolved from Key Vault
    secret_names: list[str] = []         # NEW: list of secret names to pull
```

When `acr_login_server` is set, use it as the image prefix and pass ACR credentials
as `ImageRegistryCredential` in the `ContainerGroup` spec instead of Docker Hub credentials.

---

## Step 6 — CI Terraform Validation

Add Terraform format-check and validate to the existing `lint` job. No plan/apply
runs in CI — those require Azure credentials and are manual operations.

### `.github/workflows/ci.yml`

```yaml
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]" mypy
      - run: ruff check src tests
      - run: mypy src
      # Terraform validation (no Azure credentials needed)
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.7"
      - run: terraform -chdir=infra fmt -check -recursive
      - run: terraform -chdir=infra init -backend=false
      - run: terraform -chdir=infra validate
```

### `infra/.gitignore`

```
.terraform/
*.tfstate
*.tfstate.backup
terraform.tfvars
.terraform.lock.hcl   # commit this if you want version-pinned providers
```

---

## Step 7 — Environment Variable Files

### `infra/environments/dev.tfvars`

```hcl
environment         = "dev"
resource_group_name = "clipsmith-rg"
location            = "eastus"
aci_sp_object_id    = ""   # fill in: az ad sp show --id <client_id> --query id -o tsv
```

### `infra/environments/prod.tfvars`

```hcl
environment         = "prod"
resource_group_name = "clipsmith-rg"
location            = "eastus"
aci_sp_object_id    = ""   # fill in for prod SP
```

Secrets are passed on the CLI or via a separate `secrets.auto.tfvars` (gitignored):

```bash
terraform apply \
  -var-file=environments/dev.tfvars \
  -var='secrets={"ANTHROPIC-API-KEY":"sk-...","TWITCH-CLIENT-ID":"..."}'
```

---

## File Layout (final state after Sprint 6)

```
infra/
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── .gitignore
├── modules/
│   ├── storage/   main.tf, variables.tf, outputs.tf
│   ├── registry/  main.tf, variables.tf, outputs.tf
│   ├── keyvault/  main.tf, variables.tf, outputs.tf
│   └── network/   main.tf, variables.tf, outputs.tf   (stub — not wired to main yet)
└── environments/
    ├── dev.tfvars
    └── prod.tfvars

src/clipsmith/
├── cloud/
│   └── azure_runner.py   MODIFIED — _resolve_secrets(); ACR ImageRegistryCredential
└── config/
    └── models.py          MODIFIED — CloudConfig gains acr_*, key_vault_uri, secret_names

.github/workflows/
└── ci.yml                 MODIFIED — terraform fmt/init/validate in lint job
```

---

## Verification Checklist

### Terraform
- [ ] `terraform -chdir=infra fmt -check -recursive` exits 0 on clean code
- [ ] `terraform -chdir=infra init -backend=false && terraform validate` exits 0
- [ ] CI lint job runs Terraform validation on every PR

### Modules
- [ ] `terraform plan -var-file=environments/dev.tfvars` shows resource group, storage account, two shares, ACR, Key Vault (no errors)
- [ ] `terraform apply` provisions all resources; outputs print ACR login server and Key Vault URI

### Key Vault
- [ ] After apply, secrets appear in Key Vault (Azure portal or `az keyvault secret list`)
- [ ] ACI service principal can `az keyvault secret show --name ANTHROPIC-API-KEY` but cannot set/delete

### ACR
- [ ] `docker login <acr-login-server> -u <admin_username> -p <admin_password>` succeeds
- [ ] `clipsmith cloud build` (or manual `docker push`) sends image to ACR instead of Docker Hub
- [ ] ACI container created with `acr_login_server` in `ImageRegistryCredential` starts successfully

### Secrets in ACI
- [ ] When `key_vault_uri` is set in config, `_resolve_secrets()` fetches values before container creation
- [ ] ACI environment variables contain resolved secret values (not Key Vault references)
- [ ] No secrets appear in `cloud run` CLI output or logs
