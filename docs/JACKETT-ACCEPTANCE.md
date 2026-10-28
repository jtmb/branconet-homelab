# Jackett security patch acceptance

Jackett 0.24.1440 now uses the patched signed Alpine image, .NET 9.0.21 and
AngleSharp 1.5.0. Exact image:
`docker.io/library/jackett-security-20261023@sha256:08f115ddcbc3e01bf5379e4c91ea594fae49666678b53ed20af889773b1ca729`.
The same-source rebuild and immutable chart update passed local validation and
Flux. Runtime self-updates are disabled; TCP startup/readiness probes are enabled.

The complete cold encrypted archive was authenticated before adoption: 39 files,
23,941,951 bytes; receipt SHA256
`83eb53812db1e113edceee01aac2ab78f16881f4239b0dccb6f6b15ffb09e940`.
All six indexers, API/admin credentials, protection keys and other original
settings passed comparison, including a controlled restart. The narrow comparison
allows only existing anti-bot cookie values to refresh: cf_clearance for eztv and
1337x, and __ddg8_/__ddg10_ for nyaasi. These source-defined public indexers have
no configured login fields; cookie names and all other values remain compared.
The original complete cookies remain in the encrypted archive.

Restart acceptance receipt SHA256:
`b032eed3e7309fdbdafaaee7a702f68ed55e25b08fc77cc9c58bdb1d6f8bbe1a`.
All three nodes passed the legacy port and ingress HTTP checks (six checks),
receipt `0eeb56230651fa90f3f213a5f130afaa54b41fb81fd7762eb496e4604778f958`.
No real indexer search, download or notification was sent by qualification.
Final browser acceptance remains pending.

The unsuppressed scan retains 12 High and three Medium legacy NuGet reference-lock
rows. The selected runtime manifests and OS have none. Both application/updater
select .NET 9.0.21; the affected runtime DLL hashes match the reviewed patch and
the old reference-lock entries select no runtime/native assets. The separate
attribution proof is `d0bb93cb07c1c7a8db36a1449545734ae86ea3b81f8c67f0441e1e7a4137ae1f`.
No metadata, analyzer or finding was suppressed. This is not a zero-finding scan.
