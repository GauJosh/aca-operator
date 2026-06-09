# Deploy SynosCD Operator to Azure Container Apps

1. Build and push the operator image

```bash
az acr build --registry myacr --image synoscd:latest .
```

2. Create secrets in Key Vault for sensitive config

```bash
az keyvault secret set \
  --vault-name my-vault \
  --name synoscd-github-app-id \
  --value <YOUR_APP_ID>

az keyvault secret set \
  --vault-name my-vault \
  --name synoscd-github-private-key \
  --value @private_key.pem
```

3. Deploy to ACA (using Terraform or Azure CLI)

```bash
az containerapp create \
  --name synoscd \
  --resource-group my-rg \
  --environment my-ace \
  --image myacr.azurecr.io/synoscd:latest \
  --cpu 0.5 \
  --memory 1Gi \
  --env-vars \
    SYNOSCD_GITHUB_APP_ID=@Microsoft.KeyVault(SecretUri=https://my-vault.vault.azure.net/secrets/synoscd-github-app-id/) \
    SYNOSCD_GITHUB_REPO_OWNER=my-org \
    SYNOSCD_GITHUB_REPO_NAME=my-config-repo \
    SYNOSCD_AZURE_SUBSCRIPTION_ID=<SUB_ID> \
    SYNOSCD_AZURE_RESOURCE_GROUP=my-rg \
    SYNOSCD_AZURE_CONTAINER_APP_ENVIRONMENT=my-ace \
    SYNOSCD_LOG_LEVEL=INFO \
  --user-assigned-identity /subscriptions/<SUB>/resourceGroups/<RG>/providers/Microsoft.ManagedIdentity/userAssignedIdentities/synoscd \
  --ingress disabled
```

4. RBAC: Grant SynosCD managed identity permissions

```bash
# Assign Contributor role to resource group (or more restrictive)
az role assignment create \
  --assignee-object-id <MANAGED_IDENTITY_PRINCIPAL_ID> \
  --role "Contributor" \
  --scope /subscriptions/<SUB_ID>/resourceGroups/<RG_NAME>
```
