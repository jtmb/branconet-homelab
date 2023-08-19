#!/bin/bash

# Define the wrapper script to run
WRAPPER_SCRIPT="/data/ip_check/runner.sh"
ANSIBLE_VARS_LOCATION="/data/ip_check/vars.yml"

# Set vars for ansible
rm -f $ANSIBLE_VARS_LOCATION
touch $ANSIBLE_VARS_LOCATION
echo a_name_record: $A_NAME_RECORD >> $ANSIBLE_VARS_LOCATION
echo cf_key: $CF_KEY >> $ANSIBLE_VARS_LOCATION
echo cf_zone_id: $CF_ZONE_ID >> $ANSIBLE_VARS_LOCATION
echo discord_webhook: $DISCORD_WEBHOOK >> $ANSIBLE_VARS_LOCATION

# Function to run the wrapper script
cd /data/ip_check
run_wrapper() {
    # You can add any necessary setup or environment variables here
    # Example: export VAR=value
    
    # Run the wrapper script
    bash "$WRAPPER_SCRIPT"
}

# Trap SIGTERM to gracefully handle container shutdown
trap 'exit 0' SIGTERM

# Loop indefinitely with a 2-minute delay between iterations
while true; do
    run_wrapper
    sleep 120  # Sleep for 2 minutes
done

# Tail Crontab
# cron && tail -f /var/log/cron.log