# Migration service coverage

Baseline source inventory is preserved. Private checks establish the recorded behavior; unresolved integrations and final retirement are tracked in MIGRATION_STATUS.md.

| Source | Chart / replacement | Namespace | Current status |
|---|---|---|---|
| bot_ruckus | apps/ruckus-bot | ruckus | Native running; private checks passed |
| bot_ruckus-db | apps/ruckus-db | ruckus | Native running; private checks passed |
| cicd_server-bootstrap | Vault Consul backend: retain consistent recovery data; retire only after native Secrets verification and user confirmation. | — | Source retained; replacement acceptance/final retirement open |
| cicd_vault | Replace secrets function with native Kubernetes Secrets and BORTUS; retain recovery until final acceptance. | — | Source retained; replacement acceptance/final retirement open |
| gamesrv_mc-exporter | apps/minecraft-exporter | games | Native running; private checks passed |
| mealie_mealie | apps/mealie | mealie | Native running; private checks passed |
| media_bazarr | media-stack/bazarr | plex | Native running; private checks passed |
| media_flaresolverr | media-stack/flaresolverr | plex | Native running; private checks passed |
| media_jackett | media-stack/jackett | plex | Native running; private checks passed |
| media_overseerr | media-stack/overseerr | plex | Native running; private checks passed |
| media_radarr | media-stack/radarr | plex | Native running; private checks passed |
| media_sonarr | media-stack/sonarr | plex | Native running; private checks passed |
| media_tautulli | media-stack/tautulli | plex | Native running; private checks passed |
| media_unpackerr | media-stack/unpackerr | plex | Native running; private checks passed |
| media_xteve | apps/xteve | plex | Native running; private checks passed |
| media_ytdl | media-stack/ytdl | plex | Native running; private checks passed |
| pi_exporter | apps/pihole-exporter | pihole | Native running; private checks passed |
| pi_pihole | apps/pihole | pihole | Native running; private checks passed |
| portainer_agent | Replace cluster-management function with BORTUS; record agent/socket dependency checks before retirement. | — | Source retained; replacement acceptance/final retirement open |
| portainer_portainer | Replace management function with BORTUS; retain Portainer database and verify feature coverage before retirement. | — | Source retained; replacement acceptance/final retirement open |
| proxy_traefik | @foundation/ingress | traefik | Native ingress/DNS ports transferred; original ACME/logs retained |
| proxy_whoami | test-stack/whoami | whoami | Native running; private checks passed |
| vault_vaultwarden | apps/vaultwarden | vaultwarden | Native running; private checks passed |
| wordpress_db | apps/wordpress-db | wordpress | Native running; private checks passed |
| wordpress_phpmyadmin | apps/phpmyadmin | wordpress | Native running; private checks passed |
| wordpress_redis-db | apps/wordpress-redis | wordpress | Native current state works; original historical state unresolved |
| wordpress_wp-app | apps/wordpress | wordpress | Native running; private checks passed |
| ws_aplb | web-app-stack/aplb | web-apps | Native running; private checks passed |
| ws_homepage | homepage | homepage | Native running; private checks passed |
| ws_lucinda | web-app-stack/lucinda-art-gallery | web-apps | Native running; private checks passed |
| ws_mcwebsite | apps/minecraft-website | web-apps | Native running; private checks passed |
| ws_santos | web-app-stack/santos-web | web-apps | Native running; private checks passed |
| 192.168.0.4/qbittorrent | media-stack/qbittorrent | plex | Native running; private checks passed |
| 192.168.0.4/GlueTun-proton | apps/gluetun | plex | Native running; private checks passed |
| 192.168.0.4/plex-plex-1 | media-stack/plex | plex | Consolidated to master configuration; playback/relocation passed; originals retained |
| 192.168.0.5/plex-plex-1 | media-stack/plex | plex | Consolidated to master configuration; playback/relocation passed; originals retained |
| 192.168.0.6/ets2-server | apps/ets2 | games | Native running; private checks passed |
| 192.168.0.6/plex-plex-1 | media-stack/plex | plex | Consolidated to master configuration; playback/relocation passed; originals retained |
| repository/media-stack/qbit-monitor | media-stack/qbit-monitor | plex | Native running; private checks passed |
| repository/test-stack/http-echo | test-stack/http-echo | http-echo | Native running; private checks passed |
| repository/web-app-stack/jtmb-dev | web-app-stack/jtmb-dev | website-stack | Native running; private checks passed |
| repository/BORTUS | apps/bortus | bortus | Native running; private checks passed |
