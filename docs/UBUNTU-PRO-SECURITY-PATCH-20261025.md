# Worker Ubuntu Pro security patch — USN-8555-1

The separate `ubuntu_pro_security_patch` role is disabled by default. It addresses [USN-8555-1](https://ubuntu.com/security/notices/USN-8555-1) on workernode2 (`192.168.0.5`) and then workernode1 (`192.168.0.6`), serially. It pins **37.2ubuntu~22.04.1** for `ubuntu-advantage-tools`, `ubuntu-pro-client` and `ubuntu-pro-client-l10n` from trusted Ubuntu Jammy security metadata. It does not select the broader cached candidate 38. Master is excluded and already has the security release.

This role does not invoke or alter `security_maintenance`, whose complete original-volume guard remains intact. The narrowly selected package transaction requires no drain, reboot, runtime change or attached-volume mutation. The intentionally detached original Ruckus volume is therefore outside this package role's checks and is not falsely declared attached.

Source entry point: `k8s-rewrite/ansible-playbook/playbooks/ubuntu-pro-security-patch.yml`; implementation: `roles/ubuntu_pro_security_patch/{defaults,tasks}/main.yml` and `files/guard.py` under the same Ansible root.

## Enforced transaction

- Explicit `ubuntu_pro_security_patch_enabled: true` is required; actual installation additionally requires `ubuntu_pro_security_patch_apply: true`. Disabled/check mode does not execute observations or installation. Enabled without apply performs and records preflight only.
- Only the exact worker hostname/address pairs, Ubuntu 22.04 Jammy amd64, running kernel `5.15.0-198-generic`, active custom containerd 2.4.2 and inactive legacy runtimes are accepted. Installed selected packages must be the reviewed version 30, the exact patched version, or the expected not-yet-installed split client.
- The read-only APT simulation uses the exact three pins and `jammy-security`. Every `Inst` must be in that set at the pinned version and security origin; all expected changes must be present. Removals and unrelated configuration rows are rejected. `dpkg --audit` must be empty.
- Actual Ansible APT uses the same three pins and security pocket, no cache refresh, no unauthenticated packages, no downgrade/force, `fail_on_autoremove`, `force-confold`, temporary `policy_rc_d: 101`, and `NEEDRESTART_MODE=l`. Existing modified dpkg conffiles are retained; there are no Pro attach/account/config commands or private credential reads. Standard signed APT configuration is used.
- Before/after checks compare every installed package name/architecture/version, allowing only these three package changes. The official tools transition from an architecture-specific package to `all` is handled as a replacement of the same exact name, not an unrelated package removal. All three final package versions must equal the security pin.
- Kernel, boot ID, containerd binary/config SHA256 and version, active runtime/kubelet PID and start timestamp, legacy service states, reboot markers and restored policy-rc.d identity must remain unchanged. All three original Node UIDs, Ready/no-pressure state, cordons and node runtime/kernel/boot metadata are checked through the existing master kubeconfig before and after each worker.
- The play stops on failure before processing the next worker. It does not roll back packages, restart services, reboot or modify storage automatically. A unique private baseline is written before installation; after and verified receipts are separate files. A failed run's log/baseline must be retained and actual state inspected before any retry.

## Prepared execution and observed checks

At 15:14 UTC on October 25, the **actual read-only guard** passed both workers: exactly the three approved `Inst` rows, version 37.2, trusted Jammy security origins, no removal, empty dpkg audit, expected host/runtime state. The cluster guard passed the three exact UIDs and Ready/no-pressure checks. Ansible syntax check passed; `--list-hosts` reported only workernode2 then workernode1. No package installation was executed by the worker preparing this source.

The parent operator's credential-in-RAM process is not accessible from the worker's execution context (`Unknown process id 4775`). Execution ownership was returned to the parent without requesting or copying credentials. The playbook reads the existing `BRANCONET_MIGRATION_SUDO_PASSWORD` environment variable directly into `ansible_become_password`; it is never included in the nonsecret request, argv, source or receipt.

Frozen source root:

`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/control-source/ubuntu-pro-patch-bf424de0530e`

`source-manifest.json` binds the four source files and dedicated inventory. The dedicated inventory retains the previously reviewed SSH options/key/addresses and uses the canonical `worker` group; the reused xTeVe inventory originally called this group `workers`, which would otherwise select no hosts. Both host selection and syntax were verified against the dedicated inventory.

The exact operator JSON is `operator-request.json` inside that frozen root. Send its contents to the existing RAM operator, not to a shell. It invokes:

```text
/home/brajam/.local/share/branconet-migration/venv/bin/ansible-playbook
  <frozen-root>/playbooks/ubuntu-pro-security-patch.yml
  -i <frozen-root>/inventory.json
  --extra-vars {"ubuntu_pro_security_patch_enabled":true,"ubuntu_pro_security_patch_apply":true,"ubuntu_pro_security_patch_receipt_dir":"/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/ubuntu-pro-security-patch-bf424de0530e"}
```

The original request included additional environment keys that the RAM operator refused before mutation. The successful parent invocation retained **only `ANSIBLE_ROLES_PATH` and `ANSIBLE_HOST_KEY_CHECKING`** in its supplied environment, preserving the same frozen source, exact package pins and worker order. Do not resend the original unfiltered request. Its unique log is `FBASE/control-logs/ubuntu-pro-security-patch-bf424de0530e.log`. Receipts go to `FBASE/ubuntu-pro-security-patch-bf424de0530e/` with unique worker basenames and `.before.json`, `.after.json`, `.verified.json` suffixes. In these abbreviations FBASE is `/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.

## Actual applied result

The parent executed the exact pinned transaction successfully on both workers on 2026-10-25. The retained Ansible recap is `ok=13`, `unreachable=0`, `failed=0`, `rescued=0` for each worker. Log SHA256: `5afb5d90fbe24978c4f63cb75358bfc6ef7fcff9445f6f9eb89490d2881338e5`.

Both verified receipts were independently re-evaluated with the same source guard against their complete before/after package and Node observations; the recomputed result equals the recorded result:

| Worker | Verified receipt under the receipt directory | SHA256 |
| --- | --- | --- |
| workernode2 | `workernode2-pahh6ev3.before.json.verified.json` | `6ba1702463cfa93b86c5f86ac5b817d601b451512e0770717791861484bbe94a` |
| workernode1 | `workernode1-v3awc5bs.before.json.verified.json` | `19a9e497abba296d6e3c15a5c7e4da11095bca7ac2fa7ae060110703c740bffb` |

Every selected package is now `37.2ubuntu~22.04.1`. The expected package split replaces `ubuntu-advantage-tools:amd64` version 30 with its `:all` security-version package, upgrades l10n and installs the matching client. The full package-map comparison found no unrelated package changes. Kernel/boot ID, containerd binary and configuration hashes/version, runtime/kubelet service PID/start identity, inactive legacy services, reboot markers and policy-rc.d identity stayed equal. All three original Node identities and Ready/no-pressure/runtime observations stayed equal. No drain, reboot, runtime restart, Pro account action or master package update occurred through this role. No image build, scan or Git operation was performed for this patch.
