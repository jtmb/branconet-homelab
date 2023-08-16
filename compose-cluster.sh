# ----------VARS
userid=$(whoami)
public_ip=$(curl icanhazip.com)
admin_pub_ip=$(echo ['"'$public_ip/32'"'])
homedir=/home/$userid/repos/media-stack
# ----------Instance IP's
master_node=192.168.0.24
worker_node_1=192.168.0.16
worker_node_2=192.168.0.19
# --------------------------------------------------------------------

cd ansible_provisioning && ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -i inventory.ini main.yml \
    --limit 'master_node' --skip-tags "reboot" --tags "containers" \
    --extra-vars "ssh_port=2002 pub_key=$pub_key \
    master_node=$master_node  \
    worker_node_1=$worker_node_1 \
    worker_node_2=$worker_node_2  \  
    ssh_cert=$HOME/.ssh/id_rsa homedir=$homedir \
    user_id=$userid  \
    PUB_IP=$public_ip \
    ansible_sudo_pass="