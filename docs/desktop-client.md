# Windows 桌面客户端

本文记录 Windows 64 桌面客户端的当前工程边界。桌面客户端用于把视频数据面移到用户设备侧：当前产品 UI 只暴露本地视频读取；百度网盘直连相关底层能力保留，但导入和播放入口已隐藏。

## 当前阶段

当前阶段包含：

- Tauri 工程脚手架。
- 前端 desktop runtime 标记。
- Tauri `desktop_health` 命令。
- Tauri `desktop_choose_local_directory` 命令。
- Tauri `desktop_native_media_url` 命令。
- Tauri `desktop_native_subtitle_file` 命令。
- 项目设置页在 desktop 下支持选择 Windows 本机文件夹并递归导入媒体文件。
- 桌面端本地媒体服务。
- 工作台播放器在 desktop + `NATIVE_LOCAL` 下使用客户端本地媒体 URL 播放文件。
- AI 问答页在 desktop + `NATIVE_LOCAL` 下使用客户端本地媒体 URL 截取课程视频帧。
- 工作台播放器在 desktop + `NATIVE_LOCAL` 下读取视频同目录同名字幕。
- 工作台视频助手、桌宠助手和 AI 问答页课程视频上下文在 desktop + `NATIVE_LOCAL` 下使用客户端读取的本机字幕。
- 百度网盘桌面端直连播放描述符与 Tauri `desktop_baidu_hls_url` 命令仍保留在底层实现中。
- 工作台播放器当前不播放 `BAIDU_NETDISK` 媒体源，而是提示该媒体源已隐藏。

当前阶段不包含：

- 离线缓存。
- 云视频托管。
- 多清晰度选择。
- 百度网盘导入和播放的产品 UI 入口。
- 百度网盘视频本机缓存。

## 目录

- `desktop/package.json`：桌面客户端构建入口。
- `desktop/src-tauri/`：Tauri Rust 工程。
- `frontend/src/ui/runtime/appRuntime.ts`：前端运行时识别，Web 为 `web`，Tauri 为 `desktop`。
- `frontend/src/ui/runtime/desktopBridge.ts`：桌面端 Tauri 命令桥接。
- `frontend/src/ui/runtime/desktopLocalDirectory.ts`：桌面端本机文件夹选择和扫描 bridge。
- `frontend/src/ui/runtime/desktopMedia.ts`：桌面端本地媒体 URL bridge。
- `frontend/src/ui/runtime/desktopSubtitle.ts`：桌面端本地字幕 bridge。
- `frontend/src/ui/runtime/desktopBaiduMedia.ts`：桌面端百度 HLS URL bridge。
- `frontend/src/views/settings/ProjectSettingsPage.tsx`：桌面端本机文件夹导入入口。
- `frontend/src/views/workbench/components/VideoPane.tsx`：桌面端 `NATIVE_LOCAL` 播放器接入点。

桌面客户端构建图标复用 `frontend/public/favicon.ico`，不在 `desktop/` 下维护第二份品牌图标。Tauri `frontendDist` 从 `desktop/src-tauri/` 解析，因此指向 `../../frontend/dist`。

## 本地媒体服务

桌面端本地媒体服务由 Tauri 进程启动：

- 只监听 `127.0.0.1`。
- 使用随机端口。
- 前端通过 `desktop_native_media_url` 为单个素材注册播放 URL。
- URL 使用随机 token，不暴露真实本地文件路径。
- 支持 `GET`、`HEAD`、`OPTIONS`。
- 支持 HTTP `Range`，用于 `<video>` 拖动和分段读取。
- 返回 CORS 头，允许播放器画面截帧。
- `Cache-Control` 为 `no-store`。
- 工作台播放器和 AI 问答页课程视频帧截取共用这条本地媒体 URL 数据面。

路径边界固定为：

```text
canonical(projectRoot / learningObjectRoot / materialId)
```

其中：

- `projectRoot` 必须是可访问目录。
- `learningObjectRoot` 必须是相对路径。
- `materialId` 必须是相对路径。
- 最终文件必须位于 `canonical(projectRoot / learningObjectRoot)` 下。

这条路径语义复用现有项目存储配置；本阶段不新增路径兼容层。

## 本地文件夹导入

Windows 桌面端本地文件夹导入使用客户端扫描、云端建树的数据流：

- 前端在 Tauri desktop 下通过 `desktop_choose_local_directory` 打开系统目录选择器。
- Tauri 进程 canonicalize 用户选择的目录，并递归扫描可导入媒体文件。
- Tauri 只把 `projectRoot`、`rootTitle` 和 POSIX 形式的 `relativeFilePaths` 返回给前端。
- 前端调用 `import-learning-objects-from-native-local` 后端接口提交扫描结果。
- 后端不访问用户 Windows 文件系统，只校验路径语义并按相对路径权威重建学习对象树。
- 后端把项目材料源绑定为 `NATIVE_LOCAL`，并保存 `ProjectStorageConfig(projectRoot, learningObjectRoot=".")`。
- `NATIVE_LOCAL` 导入使用 `MANUAL_SYNC`，避免线上后端在启动或读取时扫描用户本机路径。
- 未出现在本次扫描结果中的旧实例如果仍被复述点引用，会标记为 `MISSING` 供后续迁移锚点；如果没有任何复述点引用，会在同步时直接删除。

当前可导入媒体扩展为 `.mp4`、`.mov`、`.mkv`、`.webm`、`.mp3`、`.wav`、`.m4a`、`.aac`、`.flac`、`.ogg`、`.opus`。导入时不跟随符号链接和快捷方式，避免目录边界不清。

## 本地字幕读取

桌面端本地字幕读取由 Tauri command 完成：

- 前端通过 `desktop_native_subtitle_file` 请求本机字幕。
- 字幕查找规则与现有产品语义一致：只匹配视频同目录同名字幕。
- 支持 `.srt`、`.vtt`、`.ass`、`.ssa`。
- 同一目录下多个格式同时存在时，优先级为 `.srt`、`.vtt`、`.ass`、`.ssa`。
- Rust 端只读取字幕原文和文件名/格式，字幕解析仍复用前端现有解析器。
- 字幕文件路径必须位于素材文件同一个 canonical 父目录下。
- 前端只在 Tauri desktop + `NATIVE_LOCAL` 且存在项目存储配置时走本地字幕 command。
- 用户导入并绑定到实例的字幕资产优先于同目录同名字幕；没有导入字幕时，Web、本地浏览器目录和服务端文件继续使用原有同目录同名字幕链路。`BAIDU_NETDISK` 媒体源当前不在播放器里读取字幕。

这条路径让桌面端本地视频的播放器字幕、工作台视频助手字幕上下文、桌宠助手字幕上下文和 AI 问答页课程视频上下文都由客户端读取本机字幕；云服务器不读取用户本机路径。

## 百度网盘直连播放

Windows 桌面端百度网盘视频播放底层链路仍保留，但当前产品 UI 不调用该链路。历史实现使用两段式链路：

- 云端后端校验登录态和项目访问权，读取用户已绑定的百度网盘账号 token。
- 云端后端请求百度 HLS playlist，把 playlist 内分片补成绝对百度 URL，并通过 `baidu-direct-playback` API 返回给桌面客户端。
- Tauri 端通过 `desktop_baidu_hls_url` 把 playlist 注册到本机媒体服务。
- 工作台播放器播放 `http://127.0.0.1:<port>/baidu-hls/<token>/playlist.m3u8`。
- Tauri 本机服务把 playlist 中的分片改写为本机 `/baidu-hls/<token>/segment?u=...`。
- 分片请求由用户电脑上的 Tauri 进程访问百度上游 URL，再返回给 WebView。

该链路下，百度网盘视频分片流量路径为：

```text
用户 Windows 客户端 -> 百度网盘
```

不是：

```text
用户 Windows 客户端 -> 自托管云服务器 -> 百度网盘
```

云服务器仍参与登录、权限校验、账号 token 解密和 playlist 小数据获取，但不转发视频分片。

本机百度 HLS 代理边界：

- 只监听 `127.0.0.1`。
- 使用随机端口。
- 每个 playlist 使用随机 token。
- 上游分片 URL 只允许 `https://*.baidu.com`、`https://*.baidupcs.com` 和 `https://*.bdstatic.com`。
- 支持 `GET`、`HEAD`、`OPTIONS`。
- 支持透传 `Range`。
- 返回本机 CORS 头，允许 HLS.js 在 Tauri WebView 中读取。
- `Cache-Control` 为 `no-store`。

当前不做：

- 本机缓存。
- 离线播放。
- 断点续传。
- 缓存空间上限。
- 播放 URL 过期后的自动刷新。
- Web 端百度网盘直连播放。

## 运行

桌面客户端复用 `frontend` 的 Vite 构建。开发时需要先安装前端和桌面端依赖：

```powershell
pnpm --dir frontend install
pnpm --dir desktop install
```

Tauri 2.11 的当前依赖链需要 Rust `1.88`。当前桌面工程声明最低 Rust 版本为 `1.88`，并通过 `desktop/src-tauri/rust-toolchain.toml` 固定桌面工程使用 `1.88.0`；如果本机尚未安装该工具链，需要先安装或更新：

```powershell
rustup toolchain install 1.88.0
```

如果桌面客户端要访问线上云端 API，需要在启动前设置：

```powershell
$env:VITE_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir desktop dev
```

未设置 `VITE_API_BASE_URL` 时，前端仍使用默认 `/api`，这只适合同源 Web 运行或 Vite 代理场景。

线上后端同时需要允许 Windows Tauri 生产客户端来源：

```env
LEARNINGPYRAMID_ALLOWED_ORIGINS=https://plm.xuebao.chat,http://tauri.localhost
```

`LEARNINGPYRAMID_ALLOWED_ORIGINS` 会覆盖默认的 `LEARNINGPYRAMID_PUBLIC_ORIGIN` 推导，因此必须同时保留 Web 站点来源 `https://plm.xuebao.chat`。开发地址如 `http://127.0.0.1:1420` 只应在开发环境单独配置。

## 构建

```powershell
$env:VITE_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir desktop build
```

正式分发 Windows 安装包前需要补齐代码签名和发布流程；当前阶段不处理签名、自动更新或安装包分发策略。

## 线上底层链路验证

百度网盘直连播放当前已从产品 UI 隐藏；以下脚本只保留为底层链路的只读验证工具，不代表当前工作台会暴露或调用该播放路径：

```powershell
python tools/verify_desktop_mvp_live.py --server-host plm.xuebao.chat --server-user root --ssh-port 22 --subject-id subj_000006 --scoped-project-id proj_000001
```

该脚本会通过 SSH 进入线上 Docker app 容器，优先验证当前学习对象树中的 `BAIDU_NETDISK` + `HLS` 实例，并检查：

- 线上 app 容器健康状态、`/api/health/live` 和 `/api/system/capabilities`。
- `baidu-direct-playback` 描述符包含有效 `playlistText` 和 `upstreamUrl`。
- playlist 中的百度上游 URL 符合桌面端代理白名单，且已签名媒体 URL 不被追加 `access_token`。
- 抽样 HLS 分片 `Range` 请求能从百度上游返回 `200/206` 和实际字节。
- 服务器最近日志没有 `/segments/` 分片流量。
- 本地 release exe、NSIS 安装包和桌面进程本机监听存在。

该脚本不写线上学习数据，不替代当前产品 UI 验收。当前 UI 验收应确认百度网盘导入和播放入口不可见，历史 `BAIDU_NETDISK` 实例显示为隐藏媒体源。

学习数据同步闭环使用隔离 SQLite store 验证：

```powershell
python tools/verify_desktop_learning_data_sync.py
```

该脚本会创建临时学科和材料，导入浏览器目录扫描样本，写入视频播放进度，提交并编辑复述点，追加一条复习理解，然后重新构造后端运行时读回数据。覆盖范围包括：

- 播放进度 range 归并、持久化和重载读回。
- 复述点问题、答案和视频锚点持久化。
- 复习提交时追加的理解持久化。
- 按实例反查复述点索引。

该脚本默认不连接线上服务器，也不写真实用户项目数据。

## 后续方向

后续应继续补齐：

- 百度网盘播放 URL 过期后的自动刷新。
- 百度网盘视频缓存到本机。
- 断点续传。
- 缓存空间上限。
- 缓存清理。
- 弱网重试。
- 离线播放。
- 本地字幕识别。

现有服务端百度 HLS 代理仍保留给 Web 端使用；Windows 桌面端工作台播放器已改为本机直连百度分片。
