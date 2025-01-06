#!/bin/sh
apk add curl
echo "Contents of /tmp/gluetun/forwarded_port:"
cat /tmp/gluetun/forwarded_port
tcpport=$(cat /tmp/gluetun/forwarded_port)
echo "tcpport is set to $tcpport"
echo "Setting listen_port to $tcpport"
curl --cookie-jar /tmp/cookie.txt -i --header 'Referer: http://192.168.0.5:8112' --data 'username=admin&password=admin!' http://192.168.0.5:8112/api/v2/auth/login
curl -s -b /tmp/cookie.txt "http://192.168.0.5:8112/api/v2/app/setPreferences" -d 'json={"listen_port": "'"$tcpport"'"}'
while :; do sleep 1; done
