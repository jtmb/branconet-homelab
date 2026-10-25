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

## Remaining acceptance

The original shell monitor rejects204 and the renamed cookie. Its compatible
repair preserves notifications and state, removes credential-value error dumps,
uses pipe FDs for credentials and verified tmpfs for session files. The exact
patched artifact has zero findings, but cold-state cutover and actual automatic
queue/port/alert operation remain pending at this checkpoint. Normal browser
acceptance and the whole-cluster goal remain open. Preserve all failed checks and
the old image/complete cold profile together for recovery.
