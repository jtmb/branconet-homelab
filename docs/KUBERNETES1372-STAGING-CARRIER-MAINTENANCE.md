# Applied normal-carrier maintenance patch

The proposal is `H/staging-carrier-maintenance-fix.patch` (3,252 bytes), SHA256
`232978e8662db782ab581c965fc849f526c9b2238a26177085dd415ce474f74a`.
It was applied only after native apply completed successfully on all three
nodes, terminal run `56f152a9adc044478db62e3cacc65288`.
`H/staging-carrier-maintenance-applied.json` records this source maintenance;
the completed staging operation was not replayed. This small patch remains
durable source evidence, not disposable build output.

Its exact source base remains `staging.py`, SHA256
`9ef6a287adadc82852b633a9ff282a065c80c01b9c4b60686a62dc9458a73c41`.
The resulting source SHA256 is
`561dae0a1d40c63e767e4d56f28e8e6a519db6395c31206edf300ba8201ef0d7`.
The original byte-for-byte controller is already protected at
`H/kubernetes1372-native-stage/transport-repair/original-staging.py`.

The patch changes only the normal authentication carrier and bounded diagnostic
handling: separate `sudo -k` timestamp reset; isolated password-only
`sudo -S -p '' -v` authentication without `-k`; then `sudo -n` with the binary
stream. A background reader continuously hashes stderr in bounded chunks so a
full stderr pipe cannot block the stream. Raw stderr and credentials are not
saved. Existing metadata, identity, budget, exclusive-path, intent, backup and
no-replay guards remain unchanged, and the remote helper is untouched.

The coordinator's actual harmless carrier comparison and completed nine-file
transport-repair stage supply runtime evidence for this carrier pattern. This
proposal did not repeat those probes, stage binaries, invoke cluster validation
or run tests during the active apply.

Applying the patch later creates a **new source hash**, not a revised identity
for the old operation. Never rebase the original ownership hash, rewrite the
closed intent, remove the failure records, or rerun the old stage generation.
The completed repair receipts and their binary evidence remain authoritative
for this upgrade. Any future staging generation must explicitly bind its fresh
source, identities, ownership and unique receipt namespace before writes; this
patch does not allocate one or bypass the current root's existing-intent guards.
