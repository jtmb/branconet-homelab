# Migration service coverage

Source: evidence/live-inventory.json. Every entry is pending until data/application checks are recorded. Application replacement is a contract to validate, not permission to discard source data.

| Source | Chart / replacement | Namespace | Status |
|---|---|---|---|
| bot_ruckus | apps/ruckus-bot | ruckus | pending |
| bot_ruckus-db | apps/ruckus-db | ruckus | pending |
| cicd_server-bootstrap | Vault Consul backend: retain consistent recovery data; retire only after native Secrets verification and user confirmation. | — | pending |
| cicd_vault | Replace secrets function with native Kubernetes Secrets and BORTUS; retain recovery until final acceptance. | — | pending |
| gamesrv_mc-exporter | apps/minecraft-exporter | games | pending |
| mealie_mealie | apps/mealie | mealie | pending |
| media_bazarr | media-stack/bazarr | plex | pending |
| media_flaresolverr | media-stack/flaresolverr | plex | pending |
| media_jackett | media-stack/jackett | plex | pending |
| media_overseerr | media-stack/overseerr | plex | pending |
| media_radarr | media-stack/radarr | plex | pending |
| media_sonarr | media-stack/sonarr | plex | pending |
| media_tautulli | media-stack/tautulli | plex | pending |
| media_unpackerr | media-stack/unpackerr | plex | pending |
| media_xteve | apps/xteve | plex | pending |
| media_ytdl | media-stack/ytdl | plex | pending |
| pi_exporter | apps/pihole-exporter | pihole | pending |
| pi_pihole | apps/pihole | pihole | pending |
| portainer_agent | Replace cluster-management function with BORTUS; record agent/socket dependency checks before retirement. | — | pending |
| portainer_portainer | Replace management function with BORTUS; retain Portainer database and verify feature coverage before retirement. | — | pending |
| proxy_traefik | @foundation/ingress | traefik | pending |
| proxy_whoami | test-stack/whoami | whoami | pending |
| vault_vaultwarden | apps/vaultwarden | vaultwarden | pending |
| wordpress_db | apps/wordpress-db | wordpress | pending |
| wordpress_phpmyadmin | apps/phpmyadmin | wordpress | pending |
| wordpress_redis-db | apps/wordpress-redis | wordpress | pending |
| wordpress_wp-app | apps/wordpress | wordpress | pending |
| ws_aplb | web-app-stack/aplb | web-apps | pending |
| ws_homepage | homepage | homepage | pending |
| ws_lucinda | web-app-stack/lucinda-art-gallery | web-apps | pending |
| ws_mcwebsite | apps/minecraft-website | web-apps | pending |
| ws_santos | web-app-stack/santos-web | web-apps | pending |
| 192.168.0.4/qbittorrent | media-stack/qbittorrent | plex | pending |
| 192.168.0.4/GlueTun-proton | apps/gluetun | plex | pending |
| 192.168.0.4/plex-plex-1 | media-stack/plex | plex | pending |
| 192.168.0.5/plex-plex-1 | media-stack/plex | plex | pending |
| 192.168.0.6/ets2-server | apps/ets2 | games | pending |
| 192.168.0.6/plex-plex-1 | media-stack/plex | plex | pending |
| repository/media-stack/qbit-monitor | media-stack/qbit-monitor | plex | pending |
| repository/test-stack/http-echo | test-stack/http-echo | http-echo | pending |
| repository/web-app-stack/jtmb-dev | web-app-stack/jtmb-dev | website-stack | pending |
| repository/BORTUS | apps/bortus | bortus | delegated-pending |

Detailed image, mount, route and test fields: [service-register.json](evidence/service-register.json).
