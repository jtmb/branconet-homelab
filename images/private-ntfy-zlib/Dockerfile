# Supply only the exact public package from inputs.json in the build context.
# No network, repository update, ntfy rebuild, or untrusted APK installation.
FROM docker.io/binwiederhier/ntfy@sha256:6ceb27333175e3ce7d021bb883658858f2b8b883db316a73d0755dfa0b306fc4
USER 0:0
RUN --mount=type=bind,source=zlib-1.4-r0.apk,target=/tmp/zlib-fixed.apk,readonly \
    echo "7b05bc778b8b25cd880835b40114182bd4d1581717504d0129c810c0a14291cb  /tmp/zlib-fixed.apk" | sha256sum -c - \
    && apk verify /tmp/zlib-fixed.apk \
    && apk --repositories-file /dev/null add --no-cache --no-network /tmp/zlib-fixed.apk
USER 1000:1000
ENTRYPOINT ["ntfy"]
