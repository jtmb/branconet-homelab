# ----------VARS
key_pair=$(cat ~/.ssh/id_rsa.pub)
userid=$(whoami)
public_ip=$(curl icanhazip.com)
admin_pub_ip=$(echo ['"'$public_ip/32'"'])
echo "userid=$userid" > docker-compose/jenkins/.env
sudo_pass=$(cat ~/secrets/sudo_pass)
pub_key=$(cat ~/.ssh/id_rsa.pub)
# ----------Instance IP's
master_node=192.168.0.24
worker_node_1=192.168.0.16
worker_node_2=192.168.0.19
# --------------------------------------------------------------------

cd ansible_provisioning && ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -i inventory.ini main.yml \
    --ask-become-pass --ask-pass --limit 'all' --skip-tags "jenkins" --tags "swarm" \
    --extra-vars "ssh_port=2002 pub_key=$pub_key \
    master_node=$master_node  \
    worker_node_1=$worker_node_1 \
    worker_node_2=$worker_node_2  \  
    ssh_cert=$HOME/.ssh/id_rsa \
    user_id=$userid pub_key=$pub_key \
    PUB_IP=$public_ip"