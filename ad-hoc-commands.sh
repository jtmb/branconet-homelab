# ----------VARS
userid=$(whoami)
homedir=/home/$userid/repos/media-stack
public_ip=$(curl icanhazip.com)
admin_pub_ip=$(echo ['"'$public_ip/32'"'])
# -----------------Vault Auth
source $homedir/ansible_provisioning/wrapper-scripts/vault-auth.sh
# --------------------------Vault VARS
ANSIBLE_SUDO_PASS=$(vault kv get -field=admin_pwd kv/admin_pass)
# ---------Instance IP's
master_node=$(vault kv get -field=ip kv/master_node)
worker_node_1=$(vault kv get -field=ip kv/worker_node_1)
worker_node_2=$(vault kv get -field=ip kv/worker_node_2)
# --------------------------------------------------------------------

cd ansible_provisioning && ansible all -m ansible.builtin.shell -a 'rm -rfv /home/ubuntu/container-program-files/plex_smb_share/' \
    --extra-vars "ssh_port=2002 \
    master_node=$master_node  \
    worker_node_1=$worker_node_1 \
    worker_node_2=$worker_node_2  \  
    homedir=$homedir \
    user_id=$userid  \
    ssh_cert=$HOME/.ssh/id_rsa PUB_IP=$public_ip \
    ssh_user=james ansible_become=true \
    ansible_sudo_pass=$ANSIBLE_SUDO_PASS"


