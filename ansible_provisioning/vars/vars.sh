# ###########################################################################################################################################################
# #                                                              !!!SET VARS HERE!!!                                                                      # #
# #   Vars must be set in order for ansible deploy to work. If you are unsure about what these VARS do, search for them in the project and get familiar.  # #
#############################################################################################################################################################


# GENERAL VARS
userid=$(whoami)
homedir=/home/$userid/repos/branconet-homelab
public_ip=$(curl icanhazip.com)
admin_pub_ip=$(echo ['"'$public_ip/32'"'])

# VAULT AUTH
source $homedir/ansible_provisioning/wrapper-scripts/vault-auth.sh 

# ANSIBLE VARS
ANSIBLE_SUDO_PASS=$(vault kv get -field=admin_pwd kv/admin_pass)
ANSIBLE_SSH_USER=$(vault kv get -field=admin_usr kv/admin_user)
SSH_PORT=$(vault kv get -field=port kv/ssh_port)
container_volumes_location=$(vault kv get -field=value kv/container_volumes_location)
nfs_volumes_location=/mnt/nfs-container-volumes

# INSTANCE IP's
master_node=192.168.0.5
worker_node_1=192.168.0.9
worker_node_2=192.168.0.8
mini_linux=192.168.0.4
truenas=192.168.0.3

# DNS
cf_key=$(vault kv get -field=key kv/cf_key)
cf_zone_id=$(vault kv get -field=id kv/cf_zone_id)
domain_name=$(vault kv get -field=value kv/domain_name)
lan_domain_name=$(vault kv get -field=value kv/lan_domain_name)
discord_webhook=$(vault kv get -field=value kv/discord_webhook)
email=$(vault kv get -field=value kv/email)

# VPN
nord_user=$(vault kv get -field=value kv/nord_user)
nord_pass=$(vault kv get -field=value kv/nord_password)

# BOTS
RUCKUS_BOT_TOKEN=$(vault kv get -field=value kv/ruckus_bot_token)