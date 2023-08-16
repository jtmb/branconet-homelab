AUTH_TOKEN=$(cat /$HOME/.secrets/vault_token)
VAULT_SERVER=$(cat /$HOME/.secrets/vault_server)
export VAULT_ADDR=$VAULT_SERVER
export VAULT_TOKEN=$AUTH_TOKEN
vault login $VAULT_TOKEN