# xTeVe media qualification

Run the helper on masternode using its existing kubectl context. Default mode
prints the plan. The actual configured-pipeline command is:

```sh
python3 -B qualify-xteve-media.py --execute --configured-ffmpeg-only \
  --output-dir /home/james/.local/share/branconet-migration/<new-directory>
```

The finite Pod uses exact old/new images and a cached Python reader on
workernode2. It has a random namespace, deny-all ingress/egress, no API token,
no host networking/PID/IPC, no Secrets or PVCs, read-only roots, dropped
capabilities, resource limits and a900-second deadline. Image pulling is disabled.
Only synthetic emptyDir media is used. Cleanup checks recorded resource UIDs;
isolation remains if Pod deletion is uncertain.

The four-second H264/AAC transport-stream input is served over localhost. Both
FFmpeg versions run the measured production flags:

```text
-hide_banner -loglevel error -i [URL] -c copy -c:a ac3 -f mpegts pipe:1
```

One candidate decoder compares old/new outputs: all100 video-frame hashes must
equal the input; audio must decode without errors; video remains320x180/25fps;
AC3 remains stereo48kHz. Explicit gates cover duration, monotonic DTS and A/V
offsets. Versions, commands, synthetic media/probes, hashes and cleanup UIDs
remain in the private receipt directory.

October25 configured-FFmpeg qualification passed, including deletion of all three
owned resources:
`/home/james/.local/share/branconet-migration/xteve-media-20261025-r4/receipt.json`.

Earlier full-backend failures remain retained. The original VLC image's AAC remux
failed decoding for MP4 and transport-stream input; its AC3 remux produced corrupt
and duplicate-timestamp packets. These failures are not waived into a full-backend
pass. The configured-FFmpeg result makes no VLC acceptance claim. Diagnostic
full-backend mode uses upstream stdout remux options, a harness-only vlc://quit
EOF marker, and explicit fork/wait for the vendor getppid root accommodation.
Its VLC input is the candidate's AC3 transport-stream output.

This fixture does not prove real provider access, reconnects, long-running
buffering, every codec, hardware acceleration or xTeVe startup/data preservation.
Application, cold-archive, routes and native identity acceptance remain separate.
