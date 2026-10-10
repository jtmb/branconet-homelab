# <h1> branconet-homelab

My personal highly avilable, customizable homelab as code deployment & pipeline which features:

- Ansible
- Docker swarm
- Traefik
- Rancher
- GlusterFS
- DNS roundrobbin setup
- Hashicorp Vault
- Fail2Ban
- ZFS
- Backups as service
- Highly available monitoring stack
- Highly available media stack
- Highly available webhosting
- Custom image build pipeline


##### ANSIBLE_VERSION="2.16"
##### SUPPORTED_OS_VERSIONS="UBUNTU_LTS_20.04 => 24.04"

    Run bash composecluster.sh and fill in required tags, or use "all" tags.

    Adittionaly, run adchoc commands using bash adhoccommands.sh



## BORTUS Kubernetes management app

BORTUS source is in [k8s-rewrite/front-end](k8s-rewrite/front-end). See the [workflow guide](docs/BOTRUS-WORKFLOW.md) and [deployment contract](docs/BORTUS-DEPLOYMENT.md) for setup, native Secret integration and validation.

This addition publishes the dashboard, container runtime and documentation. Kubernetes charts/provisioning and live Flux source changes remain separate from this app merge; the existing Swarm homelab sources are retained.
