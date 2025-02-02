# VARS
source ansible_provisioning/vars/vars.sh

# Ansible Playbook Consumes VARS
cd ansible_provisioning && \
     ANSIBLE_CONFIG=./ansible_provisioning/ansible.cfg ansible-playbook -i inventory.ini main.yml \
    --limit 'all' --skip-tags "images,cloudflare" --tags "torrent-stack" \
    --extra-vars "ssh_port=$SSH_PORT pub_key=$pub_key \
    master_node=$master_node  \
    worker_node_1=$worker_node_1 \
    worker_node_2=$worker_node_2  \
    mini_linux=$mini_linux  \
    truenas=$truenas  \  
    ssh_cert=$HOME/.ssh/id_ed25519 homedir=$homedir \
    container_volumes_location=$container_volumes_location nfs_volumes_location=$nfs_volumes_location \
    user_id=$userid  \
    discord_webhook=$discord_webhook discord_webhook_media=$discord_webhook_media PUB_IP=$public_ip cf_key=$cf_key cf_zone_id=$cf_zone_id domain_name=$domain_name lan_domain_name=$lan_domain_name email=$email \
    nord_user=$nord_user nord_pass=$nord_pass protonvpn_user=$protonvpn_user protonvpn_pass=$protonvpn_pass \
    ssh_user=$ANSIBLE_SSH_USER ansible_sudo_pass=$ANSIBLE_SUDO_PASS database_password=$database_password \
    RUCKUS_BOT_TOKEN=$RUCKUS_BOT_TOKEN "

# TAGS 
    # torrent-stack
    # fail2ban
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
    # docker-only
