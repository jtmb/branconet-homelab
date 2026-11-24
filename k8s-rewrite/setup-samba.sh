#!/bin/bash
set -e
echo "${BECOME_PASSWORD:?err}" | sudo -S bash -c '
mkdir -p /srv/samba-share
chown nobody:nogroup /srv/samba-share
chmod 0777 /srv/samba-share

cat > /etc/samba/smb.conf <<"SMBEOF"
[global]
   workgroup = WORKGROUP
   server string = k8s-samba
   log file = /var/log/samba/log.%m
   max log size = 1000
   logging = file
   server role = standalone server
   map to guest = bad user
   usershare allow guests = yes

[k8s-share]
   comment = Kubernetes SMB Share
   path = /srv/samba-share
   browsable = yes
   read only = no
   create mask = 0777
   directory mask = 0777
   valid users = james
SMBEOF

id james 2>/dev/null || useradd -s /usr/sbin/nologin james

echo -e "${SMB_PASSWORD:?err}\n${SMB_PASSWORD:?err}" | smbpasswd -s -a james

systemctl enable smbd --now
systemctl restart smbd
'

systemctl is-active smbd
echo "Samba setup complete"
