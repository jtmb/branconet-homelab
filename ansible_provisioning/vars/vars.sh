
# ###########################################################################################################################################################
# #                                                              !!!SET VARS HERE!!!                                                                      # #
# #   Vars must be set in order for ansible deploy to work. If you are unsure about what these VARS do, search for them in the project and get familiar.  # #
#############################################################################################################################################################


# GENERAL VARS
userid=$(whoami)
homedir=/home/$userid/repos/media-stack
public_ip=$(curl icanhazip.com)
admin_pub_ip=$(echo ['"'$public_ip/32'"'])

# VAULT AUTH
source $homedir/ansible_provisioning/wrapper-scripts/vault-auth.sh

# ANSIBLE VARS
ANSIBLE_SUDO_PASS=$(vault kv get -field=admin_pwd kv/admin_pass)
ANSIBLE_SSH_USER=$(vault kv get -field=admin_usr kv/admin_user)
SSH_PORT=$(vault kv get -field=port kv/ssh_port)
container_volumes_location=$(vault kv get -field=path kv/container_volumes_location)

# INSTANCE IP's
master_node=$(vault kv get -field=ip kv/master_node)
worker_node_1=$(vault kv get -field=ip kv/worker_node_1)
worker_node_2=$(vault kv get -field=ip kv/worker_node_2)

# CLOUDFLARE
cf_key=$(vault kv get -field=key kv/cf_key)
cf_zone_id=$(vault kv get -field=id kv/cf_zone_id)
domain_name=$(vault kv get -field=value kv/domain_name)
discord_webhook=$(vault kv get -field=value kv/discord_webhook)