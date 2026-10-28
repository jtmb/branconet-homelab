# Homepage patched runtime

Homepage1.13.2/Node22.23.4/Next16.4.1 runs through the existing private charts,
local validation publisher and Flux. Its image digest is
`7f91e85fa5d394b4be0f60686e40bf93e28e7ca0074c60754f3f02a1caa66bd4`.
The recipe retains npm/npx and supplies complete official patched dependencies,
including bundled ws, tar, ip-address and undici. Two exact upstream proxy fixes
are backported with hash-bound source guards. No scanner exclusions are added.

| Evidence | Checksum/result |
|---|---|
| Recipe source commit | `aa157513b991fad49a56bc2cc7ef3c4dc8f77819` |
| Exact archive |104,985,600 bytes; `b17231f3208da07d7174ad8158b6d998e834216ee600d55a1388c30eef673a69` |
| Fresh unsuppressed Results |Zero findings; `17a233559273020b38a83d0c7d441f737bd84d1db325506345c422c9647e754d` |
| Scan receipt | `9696446cdd9906688162c7eb63f9c3d003dc12e41ceeba3e67e682bc7a522cae` |
| Cold archive |10files/5,439,007 plaintext bytes; encrypted archive `89fef9c1a71518815d88e219fe2109fb3365501aa1ffabda184a7d597c5d0ba4` |
| Authenticated cold receipt | `f03497c0a21d2c4e76ef5701d24575a63fb16433d251772a213bb1a1cf0a259a` |
| Original live baseline | `8ca217c2d414eaf8caf1d731c503f195b49b33732f4c00e7e11d8c58b13e8369` |
| Live after comparison | `001a59acba07c847028f9f10969caad21860c43a34c6d7f572107832c4dc7daa` |

Actual Ansible cache import passed on all three nodes. The writer stopped through
Flux before the full encrypted PVC backup; the entire archive was authenticated
and the temporary read-only Pod deleted before adoption. Existing earlier
candidates, their findings/failures and the first staged artifact remain intact;
generation`r2` prevented overwrite.

The new Ready Pod has zero restarts. All nine active configuration files,
Native Secret identities/versions/content bindings, deployment settings other
than image, original Longhorn PVC and Service passed the private HMAC comparison.
The four projected native configuration files were compared as actually mounted,
separately from the complete underlying PVC archive. Mutable logs are archived
but are not configuration equality fields. Internal `/` and `/api/healthcheck`
both return200. No credential/configuration values are published.

Normal external-route, controlled-restart and final browser checks remain open;
this application checkpoint does not complete the cluster goal. No independent
restore drill or absence of undisclosed vulnerabilities is claimed.
