# qBittorrent security update and compatibility

The deployed application is5.3.0 with libtorrent2.0.15, from the supported
LinuxServer LT2.0 image plus signed Alpine3.24 updates. It keeps **Legacy
bencoded resume files**; SQLite conversion was never enabled. The exact private
recipe is `images/qbittorrent-current` in `jtmb/branconet-charts`.

| Evidence | Verified result |
|---|---|
| Deployed root digest | `9e546e0ac277ef9b241cb383bfa9157e47df3269e62481348a63f4d19b87adf8` |
| OCI archive checksum | `4a103e0632f0c53fe14ac1a3202abc103d37b11899f06661f777dac95c72f278` |
| Exact fresh scan | Zero findings; Results checksum `228a4119f8868fdd007546b6020a4bbc573ab82356c71dc9039d27a396e6f6fe` |
| Complete encrypted cold profile |533files,22,990,964 plaintext bytes; entire archive authenticated; owned reader deleted |
| Cold receipt checksum | `ceb6763ab0535b9c69d742b2ee2dbc8ce679cc6962f4d482eaf3765d3842ec2b` |
| Original API baseline checksum | `34ed4fda3db6b8e1f1953e1f53b3bfa60ae1f09084d7b9d60f62e9b3e6d418bf` |
| Successful after receipt | `5d1bc84c51a61cff805f58e96bc28f59a16e0832b122faef6a14bd7a3b8c432e` |

The authenticated comparison retained all231 torrent IDs and454 file identities,
paths, priorities, durable settings and completed progress. Original native
credential/launch Secrets, profile permissions, Longhorn claim, NAS download
claim, Gluetun image/network/DNS and resource settings were retained. The private
HMAC key stays outside Git; raw credentials, cookies and API records remain in
master-node RAM. This is not media-content or tracker-connectivity proof.

## Source-proven compatibility changes

Upstream5.3 moves27 WebUI INI keys without changing their values, returns empty
204 for successful login, and names the cookie `QBT_SID_<configured port>`.
The observer requires a fresh unauthenticated protected request to be rejected
before submitting the unchanged native credentials.204 alone is insufficient.

The observer compares the exact documented export-directory and SMTP mappings,
the always-enabled category hierarchy, and old category fields projected from
the new response. New category sharing fields must all retain inherited defaults;
complete new responses are additionally fingerprinted. Null download-path values
map to the omitted old field. No torrent/path/priority exception was used.

The first strict after comparison exposed changed upstream defaults and the old
monitor's incompatible login/parser. Four original default values were proven
against the pre-upgrade HMAC baseline and restored, together with the original
SMTP encryption mode and current Gluetun port. The opt-in
`qbittorrent-compatibility.yml` codifies that narrow operation and refuses custom
or concurrent settings. Its actual Ansible run passed; the private receipt is
`fbce6d7dd1aa72d1f6ffe27a49896f8647fc5ee2822c80ed0b30f9d7c70a8bc9`.
It leaves Native Secrets, authentication, alert settings and torrent data intact.

Primary source: [exact5.3 upgrade implementation](https://github.com/qbittorrent/qBittorrent/blob/9213075dd5f7b352208361c6a84c1c115efc898e/src/app/upgrade.cpp),
[authentication](https://github.com/qbittorrent/qBittorrent/blob/9213075dd5f7b352208361c6a84c1c115efc898e/src/webui/api/authcontroller.cpp),
and [category representation](https://github.com/qbittorrent/qBittorrent/blob/9213075dd5f7b352208361c6a84c1c115efc898e/src/base/bittorrent/categoryoptions.cpp).

## Monitor integration

The compatible monitor repair is deployed at digest
`ff2141541ec06f04df3acd145a8a94c33f6bb9e327615ff314994efeb199c4fe`.
It preserves the original notification modules and persisted state, removes
credential-value error dumps, uses pipe FDs for credentials and verified tmpfs
for session files, and accepts both old and new authentication responses.
Its exact artifact has zero scan findings; complete encrypted cold state is
fully authenticated (receipt SHA256
`67f7be2fb4f0cc102d88c451252e10368db4d1dc9edf4380d370390ea5aff493`).

The read-only integration observer verified six real queue cycles, authenticated
requests and the automatic VPN-port write/readback performed by the running
monitor. All12,461 original notification-state bytes remain with their original
permissions. The full original231-torrent/454-file comparison passed again, along
with native credential, PVC and deployment bindings. Acceptance receipt SHA256:
`b70e7ca0091d3665cbf02d0a269c44d36b6378dfd9c468724a223ab03d4ec5f7`.
Existing production alerts remain configured; no additional test notification
was sent during this check, so it does not independently prove Discord delivery.

Homepage and qBittorrent passed all15 external HTTP/HTTPS/direct-port checks
across the three nodes (receipt SHA256
`a9dc8894641fb4c837e60540eaa35d4c77b67d0954fd78aee3a2168136057c02`).
These route checks do not claim certificate-chain validation. Final browser
acceptance and the whole-cluster goal remain open. Failed checks and original
images/complete cold archives are retained for recovery.
