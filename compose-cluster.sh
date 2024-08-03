# VARS
source ansible_provisioning/vars/vars.sh

# Ansible Playbook Consumes VARS
cd ansible_provisioning && \
     ANSIBLE_CONFIG=./ansible_provisioning/ansible.cfg ansible-playbook -i inventory.ini main.yml \
    --limit 'all' --skip-tags "reboot,images,cloudflare" --tags "dns" \
    --extra-vars "ssh_port=$SSH_PORT pub_key=$pub_key \
    master_node=$master_node  \
    worker_node_1=$worker_node_1 \
    worker_node_2=$worker_node_2  \  
    ssh_cert=$HOME/.ssh/id_ed25519 homedir=$homedir \
    container_volumes_location=$container_volumes_location \
    user_id=$userid  \
    discord_webhook=$discord_webhook PUB_IP=$public_ip cf_key=$cf_key cf_zone_id=$cf_zone_id domain_name=$domain_name email=$email \
    nord_user=$nord_user nord_pass=$nord_pass \
    ssh_user=$ANSIBLE_SSH_USER ansible_sudo_pass=$ANSIBLE_SUDO_PASS "

# TAGS 
    # containers
    # swarm 
    # update_ubuntu
    # pre_prov
    # backup_all
    # backup_mc
    # smb 
    # reboot 
    # dns 
    # mc 
    # ssh 
    # cloudflare
