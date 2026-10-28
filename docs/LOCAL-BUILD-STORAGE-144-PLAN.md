# Offline 128 to 144 GiB build filesystem growth

Prepared source only on 2026-10-25. No unmount, loop detach, filesystem check, resize, daemon operation or growth has been executed by this preparation. Existing artifacts, caches and user work remain in place.

Read-only metadata identifies `/mnt/f/branconet-build-storage/native-build-20261025.ext4`, inode `115123265474727363`, 137,438,953,472 bytes, ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, mounted at `/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025` through `/dev/loop0` with direct I/O and 512-byte sectors. The wrapper rechecks these identities; it does not assume the loop number is permanent. The target is 154,618,822,656 bytes on the same inode.

The setup helper retains 96/128 GiB compatibility and adds only the finite 144 GiB generation. The Ansible role accepts growth requests 0/128/144, requires the actual pinned original inode for growth, and still defaults to no execution. Both public provenance contracts accept the three exact generations. The private offloaded builder changes only its current storage size to 144 GiB; CPU/RAM/cache/build budgets, image identities, disk reserves and all other guards remain unchanged. Historical frozen sources and receipts remain untouched.

The standalone `offline-grow144.py` must run from its frozen directory under `BASE/local-build-storage-20261025`, outside the F ext4 mount, with a separately reviewed source-manifest SHA256. Its closed preservation manifest binds four ciphertexts (original and qualified Ruckus DB, Plex, qBittorrent), their completed archive receipts, the successful fresh Ruckus restore receipt, promoted after/restart receipts, and the existing SSH private/public key metadata and hashes. Key values and decrypted archive bytes are never emitted or saved. Full cipher hashes and complete age authentication are repeated before and after growth; plaintext is drained only through bounded RAM buffers.

Execution, owned by the coordinator: first install the frozen setup source at the existing root-owned CI mount-helper path (no daemon action), then take the explicit short I/O pause:

```sh
cd /home/brajam/.local/share/branconet-migration/local-build-storage-20261025
install -o root -g root -m 0700 "$FROZEN/setup.py" /usr/local/libexec/branconet-migration/mount-build-storage.py
/usr/bin/python3 -B "$FROZEN/offline-grow144.py" --apply --source-manifest-sha256 "$MANIFEST_SHA256"
```

Invoke this as WSL root from an outside directory. `$FROZEN` and `$MANIFEST_SHA256` are the exact frozen path/hash returned with this preparation; do not regenerate the preservation manifest after a mismatch. The operator must first leave this task filesystem idle, including its shell working directories and any image-transfer/readers. The wrapper never stops those processes for the operator.

The wrapper requires the installed mount helper to match its exact frozen, root-owned setup source. That helper now also holds `host-build.lock` for existing-only ordinary startup/remount operations, preventing a cooperating CI startup from remounting during offline resize. The wrapper holds the existing exclusive `host-build.lock` continuously. It refuses active build processes, process CWD/root/executable/FD/memory-map references to the filesystem, unreadable process-reference metadata, nested mounts, changed archive/key metadata, inadequate Windows C or physical F space, or changed backing/loop geometry. It uses normal `umount` only, then detaches only the still-associated exact verified loop if normal unmount did not auto-detach it. Busy or mismatched state is a refusal, never a forced/lazy unmount or a process kill.

The frozen setup helper inherits that same locked open file description, performs offline `e2fsck -p -f` with an undo file and log outside F, requires return code 0 or 1, extends only the held original regular file, and runs offline `resize2fs`. No write operation has a timeout that could kill it mid-update. The helper normally remounts and verifies the same UUID and direct I/O. The wrapper then verifies exact 144 GiB filesystem geometry, same backing inode/ownership/mode, all preservation inputs, and at least 27 GiB native free space for the unchanged 12 GiB build plus 15 GiB launch floor.

Any failure retains the new private stage receipt, undo/logs and filesystem state for inspection. There is no automatic forced recovery, rollback shrink, formatting, cache deletion, Docker/WSL shutdown or reboot. If failure occurs while offline, the wrapper does not blindly remount a potentially unhealthy filesystem. Inspect its last operation and the setup log first.

The coordinator must publish this reviewed setup helper to the existing root-owned mount-helper location before running the wrapper, then retain it in the established Ansible configuration. An older installed helper that recognizes only 96/128 GiB will reject the new generation; do not weaken that guard or invoke the old helper after growth. The source-only preparation does not install it or reconfigure a publisher. Reverify the source manifest immediately before executing the standalone wrapper; the existing builder independently measures live space and identity before its eventual build.

## Bound resume after the first safe refusal

The coordinator's first execution authenticated all four ciphers and all 13 preservation inputs, then normally unmounted the global task mount. It refused before filesystem check/truncation/resize because a private `wsl-pro.service` mount namespace retained the autoclear loop. The immutable failed receipt is `offline-grow144-0ce6f9e2cbf74c6fabaa415f63d16a29.json`, SHA256 `d8f36ad7c87fc2c36a9b0898ba1a6b5a5f796ba01cd79dcad9107cf27307351f` under the outside evidence root. The original source manifest is `970142267f95f7f903c093ca57fe2958c56a55fc921404891f9d00c236f2e0bb`.

During read-only resume preparation the old service process/namespace disappeared naturally: `wsl-pro.service` reported `activating/auto-restart`, MainPID 0; `losetup` reported no loop devices; all visible process mount namespaces had no task mount or loop0 mount. No process, service or namespace was changed by the worker. The backing file remains exactly 128 GiB, original inode/ownership/mode/UUID, and the offline ext4 header reports `clean`, 33,554,432 blocks of 4096 bytes. Final unmount metadata flushing advanced the backing mtime to exactly `1792943668475508900` ns; the resume source pins that observed detached state separately from the earlier pre-unmount mtime.

The narrower `offline-resume144.py` therefore performs **no namespace unmount at all**. It refuses if the old loop is reused, any loop still associates the backing file, any process namespace contains the task mount, any process holds a device/CWD/FD/map reference, a builder is active, or the exact detached state changed. It continuously holds the same build lock, verifies the original failed receipt and every frozen source, verifies the installed fenced helper hash, and invokes only original setup SHA256 `1992fdc6134ef44a8dc54f68da7559d386a8bb34bd4504fa15cf3164d79a4b8b` with the inherited lock. No normal 128 GiB remount or retry of the first wrapper is needed.

After root reviews the separate frozen resume-source manifest, run from the same outside evidence directory:

```sh
python3 -B "$RESUME_FROZEN/offline-resume144.py" --apply --resume-source-manifest-sha256 "$RESUME_MANIFEST_SHA256"
```

The original frozen bundle and failed receipt must remain present and byte-identical. The resume repeats the 15 GiB launch floors, same-inode geometry/direct-I/O checks and all original archive/key/receipt hash, metadata and complete age-authentication checks after growth. It links its fresh private receipt to the original full before proof. A renewed namespace reference is a refusal requiring review, not permission to unmount another namespace. This resume was prepared and syntax-checked only; execution remains the coordinator's operation.

## Executed outcome

The coordinator subsequently executed the detached-only resume successfully. Its receipt `BASE/local-build-storage-20261025/offline-resume144-8e334d52397049b6aca9c48cb1eeaa7f.json` has SHA256 `002e256dd4cb2517a74bb71887cc536a67cea0c90e5bdc255077492f6c853e54`; this receipt was independently read and its hash verified. It completed at `2026-10-25T16:02:26.282082+00:00` with operation `same_inode_growth_original_preservation_verified`.

The filesystem is mounted at exactly 144 GiB on the original inode `115123265474727363` and UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, with direct I/O true and 512-byte loop sectors. All 13 original preservation inputs matched; all four encrypted archives passed complete age authentication. Native free space in the completion receipt was 43,980,124,160 bytes. This is Linux build-filesystem capacity, not a claim of Windows disk recovery.

The linked setup receipt is `storage-fda57611aabc43478190ffe489ec62c4.json`, SHA256 `9e659a2eee5543d05e8db95e7e66e395a64bc99dbf709a56e757f82bb24fb53f`; it records growth from 137,438,953,472 to 154,618,822,656 bytes, without creation or formatting. The earlier refused receipt and all before evidence remain retained. The private service namespace released naturally before this resume; no process/service kill, namespace unmount, WSL/Docker shutdown or reboot was used by the successful resume.
