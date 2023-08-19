# VARS
source ansible_provisioning/vars/vars.sh

# Ansible Playbook Consumes VARS
cd ansible_provisioning && ansible all -m ansible.builtin.shell -a 'rm -rfv /home/ubuntu/container-program-files/plex_smb_share/' \
    --extra-vars "ssh_port=$SSH_PORT pub_key=$pub_key \
    master_node=$master_node  \
    worker_node_1=$worker_node_1 \
    worker_node_2=$worker_node_2  \  
    ssh_cert=$HOME/.ssh/id_rsa homedir=$homedir \
    container_volumes_location=$container_volumes_location \
    user_id=$userid  \
    PUB_IP=$public_ip cf_key=$cf_key cf_zone_id=$cf_zone_id domain_name=$domain_name discord_webook=$discord_webook \
    ssh_user=$ANSIBLE_SSH_USER ansible_sudo_pass=$ANSIBLE_SUDO_PASS"

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


