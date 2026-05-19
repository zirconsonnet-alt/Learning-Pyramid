# Debug Report: Windows desktop Baidu HLS playback

- Symptom: Windows Tauri client showed `连接百度网盘视频流失败` when opening Baidu Netdisk videos.
- Root cause: Production `baidu-direct-playback` returned HLS playlists whose segment URLs used Baidu PCS CDN host `yqall06.baidupcs.com`. The Tauri local proxy allowlist only accepted `*.baidu.com` and `*.bdstatic.com`, so `desktop_baidu_hls_url` rejected the playlist before registering a localhost playback URL. The React catch block also hid Tauri string rejections behind a generic message.
- Fix: Added `*.baidupcs.com` to the explicit Tauri upstream allowlist, added Rust regression tests for accepted/rejected hosts and playlist normalization, and made `VideoPane` display non-empty string errors returned by Tauri commands.
- Evidence: Server-side sanitized probe generated real direct playback descriptors for `inst_00000091`, `inst_00000096`, `inst_00000098`, and `inst_00000099`; all had segment host `yqall06.baidupcs.com`, which the old allowlist blocked. After rebuild, the new Tauri process listened on `127.0.0.1:55427`, established an outbound 443 connection from the desktop process, and production logs still showed `/segments/` count `0`.
- Regression test: `desktop/src-tauri/src/lib.rs` unit tests under `#[cfg(test)]`.
- Verification run: `cargo +1.88.0 test`, `pnpm --dir frontend exec tsc -b --pretty false`, `cargo +1.88.0 fmt --check`, `pnpm --dir desktop build`.
- Follow-up symptom: `inst_00000001` and `inst_00000002` later played black and HLS.js reported `百度网盘视频流加载失败，请稍后重试。`
- Second root cause: those instances used signed `v2-ant.baidu.com` segment URLs. The raw signed URLs returned `206`, but the backend direct playlist rewrite appended `access_token`, after which Baidu returned `403` with `login method error`.
- Second fix: preserve already signed Baidu media URLs and only append `access_token` to unsigned Baidu URLs.
- Second regression test: `tests/test_baidu_netdisk_client.py` now covers signed media URLs retaining their query and unsigned relative Baidu URLs receiving `access_token`.
- Status: DONE_WITH_CONCERNS. The direct URL generation roots are verified; full visual playback still depends on the opened Windows Tauri window after production deployment.
