# http-echo security patch acceptance

The exact original1.0.0 source was rebuilt with Go1.26.10 and pinned current
static distroless runtime. Application source/flags, user65532, working directory,
original Longhorn claim, resources, Service and ingress specifications remain.
Image: `docker.io/library/http-echo-security-20261023@sha256:451c628e3f7587cfa4469131c7429e7b960bb1131b63a4d72e7622cc9284372a`.

All three nodes have the verified artifact. Local validation published the chart
and Flux rolled it out. Native Service and all three existing ingress HTTP
responses match the original status/body/version/location, with no application
specification change except image. The app has no application Secret reference;
none was created. Exact scan reports no findings, Results SHA256
`93668caabd5657db9c45a588b46986f3bad748d4d9d2eb0aea59dc522142295c`.
Functional receipt SHA256:
`8891bd05470301179c94a6dcb05e7d78fdbeae71eba5f89bf6150137ac3353cc`.
Final browser acceptance remains pending. No TLS acceptance is inferred from the
HTTP response comparison.
