# 公网版桌面连接器媒体中继设计

## 1. 目标

目标能力：

- 仅在公网 `hosted` 版启用。
- 用户从公网版下载一个 Windows 连接器。
- 连接器登录/配对后，为某个项目选择本地目录并保持常驻。
- 其他设备登录同一账号后，可通过网页访问该电脑目录下的视频资源。
- 视频流必须经过服务器中继，浏览器不直接连用户电脑。
- 默认在用户电脑本地做压缩或转封装，尽量降低“电脑上传到服务器”的带宽。

非目标：

- 不做浏览器直接跨设备访问本机磁盘。
- 不做 P2P / WebRTC 直连。
- 不在首版支持 macOS / Linux 连接器。
- 不在首版做多码率自适应，首版只做单档 HLS 或直接 Range relay。

## 2. 关键约束

必须明确的物理事实：

- 服务器下行流量省不掉。视频既然经过服务器，服务器到观看设备的出流量等于用户实际观看量。
- 能优化的是两段：
  - 用户电脑到服务器的上行流量。
  - 同一视频被重复观看时的回源量。
- 因此首版的成本控制要靠：
  - 本地转成低码率单档 HLS。
  - 服务器缓存分片。
  - 并发限制。

结论：

- `mp4/h264+aac/低码率`：直接 Range relay。
- `高码率 / mkv / hevc / 浏览器不兼容`：连接器本地转单档 HLS，再由服务器缓存和转发。

## 3. 产品流

### 3.1 首次使用

1. 用户在公网版登录。
2. 进入项目设置页，点击“下载桌面连接器”。
3. 安装并启动连接器。
4. 在网页端点击“生成配对码”。
5. 在连接器输入配对码，完成账号绑定。
6. 连接器选择本地目录。
7. 网页端把该连接器绑定到当前项目。
8. 连接器扫描目录并上报 manifest。
9. 服务器把项目材料源切换为 `DESKTOP_AGENT_MANIFEST`，并同步生成 `Instance/LearningObjectNode`。

### 3.2 后续使用

1. 连接器开机自启并常驻。
2. 连接器保持到服务器的 `WebSocket` 长连接。
3. 目录变更后，连接器重新扫描并推送 manifest。
4. 其他设备播放视频时，网页只请求服务器。
5. 服务器按需向连接器下发“探测 / 直传 / 转 HLS”任务。
6. 连接器把字节流或 HLS 产物上传给服务器，服务器再回给浏览器。

## 4. 总体架构

### 4.1 组件

- `Hosted App`
  - 现有 FastAPI + 前端。
  - 负责登录鉴权、项目权限、设备绑定、媒体中继、缓存、流量统计。
- `Desktop Connector`
  - Windows 常驻程序。
  - 负责配对、目录选择、manifest 扫描、媒体探测、按需读取、按需转码、向服务器回传数据。
- `Relay Cache`
  - 服务器本地磁盘缓存。
  - 缓存 HLS 分片、播放列表、媒体探测结果。

### 4.2 连接模型

- 控制面：`WebSocket`
  - 连接器主动连服务器。
  - 承载在线状态、心跳、控制命令。
- 数据面：`HTTPS`
  - 连接器主动把数据上传到服务器。
  - 服务器从内存队列或磁盘缓存向浏览器响应。

不采用“服务器反向连 agent”，因为公网用户电脑通常在 NAT 后面，不能假设可入站访问。

## 5. 播放模式

### 5.1 `relay_progressive`

适用条件：

- 文件容器/编码可直接被浏览器播放。
- 文件码率不高，或者管理员明确允许直传。

流程：

1. 浏览器请求 `GET /api/projects/{projectId}/media/instances/{instanceId}/playback`。
2. 服务器检查权限、项目绑定、连接器在线状态。
3. 服务器若无缓存的媒体探测结果，则要求连接器执行 `ffprobe`。
4. 服务器返回：

```json
{
  "mode": "relay_progressive",
  "streamId": "ms_123",
  "url": "/api/media/streams/ms_123/file",
  "contentType": "video/mp4",
  "supportsRange": true,
  "expiresAt": "2026-03-10T12:00:00Z"
}
```

5. 浏览器用 `<video>` 直接请求该 URL。
6. 服务器读取浏览器 `Range` 头，创建一次 `stream.open` 控制消息。
7. 连接器读取本地文件指定字节区间，并通过 `PUT /api/desktop-agents/stream-sessions/{streamId}/chunks` 上传。
8. 服务器边收边转发给浏览器。

### 5.2 `relay_hls`

适用条件：

- 浏览器不兼容当前文件容器/编码。
- 码率高，需要先在本地压缩。

首版固定 profile：

- 分辨率：`1280x720` 上限
- 视频编码：`h264`
- 音频编码：`aac`
- 目标码率：`1.5-2.0 Mbps`
- 分片时长：`6s`

流程：

1. 浏览器请求 playback descriptor。
2. 服务器判断应走 `relay_hls`。
3. 服务器创建 `jobId`，通过 WS 下发 `hls.start`。
4. 连接器在本地执行 `ffmpeg`，把源文件转为单档 HLS。
5. 连接器把 `master.m3u8`、`index.m3u8` 和 `.ts/.m4s` 分片上传到服务器。
6. 服务器将分片写入缓存目录，并返回：

```json
{
  "mode": "relay_hls",
  "streamId": "ms_456",
  "manifestUrl": "/api/media/streams/ms_456/master.m3u8",
  "expiresAt": "2026-03-10T12:00:00Z"
}
```

7. 前端使用 `hls.js` 播放。

### 5.3 播放决策算法

服务器按以下顺序判断：

1. 若项目材料源不是 `DESKTOP_AGENT_MANIFEST`，走现有逻辑。
2. 若连接器离线，返回 `UNREACHABLE`。
3. 若无探测结果，先触发 `probe`。
4. 若容器与编码满足：
  - `mp4/m4v/webm`
  - 浏览器兼容
  - 码率 `<= PLM_AGENT_DIRECT_MAX_MBPS`
  则走 `relay_progressive`。
5. 其他情况走 `relay_hls`。

默认环境变量：

```env
PLM_ENABLE_DESKTOP_AGENT_RELAY=true
PLM_AGENT_DIRECT_MAX_MBPS=3.0
PLM_AGENT_HLS_VIDEO_BITRATE=1200k
PLM_AGENT_HLS_AUDIO_BITRATE=96k
PLM_AGENT_HLS_SEGMENT_SECONDS=3
PLM_AGENT_CACHE_MAX_BYTES=21474836480
PLM_AGENT_CACHE_TTL_SECONDS=86400
PLM_AGENT_MAX_CONCURRENT_STREAMS_PER_AGENT=1
PLM_AGENT_MAX_CONCURRENT_VIEWERS_PER_USER=2
```

这里默认把 HLS 分片压得更小，能更稳地穿过常见反向代理的单请求大小限制，避免上传 `segmentNNN.ts` 时被网关直接回 `413 Request Entity Too Large`。

## 6. 服务端数据模型

下列对象不必全部进入 PLM 核心 spec，但必须落到服务端持久层。

### 6.1 `desktop_agents`

字段：

- `agent_id`
- `user_id`
- `device_name`
- `platform`
- `app_version`
- `status`
- `last_seen_at`
- `paired_at`
- `agent_token_hash`
- `refresh_token_hash`

约束：

- 一个 agent 只归属一个用户。
- agent token 只用于连接器，不复用用户 cookie。

### 6.2 `desktop_agent_pairing_codes`

字段：

- `pairing_code`
- `user_id`
- `expires_at`
- `used_at`
- `created_at`

约束：

- 短时有效，建议 `10` 分钟。
- 一次性使用。

### 6.3 `project_material_source_bindings`

和 `spec` 中的 `ProjectMaterialSourceBinding` 一致，持久化字段：

- `project_id`
- `source_kind`
- `desktop_agent_id`
- `source_root_label`
- `updated_at`

### 6.4 `desktop_media_probe_cache`

字段：

- `project_id`
- `instance_id`
- `agent_id`
- `manifest_generation`
- `container`
- `video_codec`
- `audio_codec`
- `duration_ms`
- `bitrate_bps`
- `width`
- `height`
- `updated_at`

### 6.5 `media_stream_sessions`

字段：

- `stream_id`
- `project_id`
- `instance_id`
- `agent_id`
- `user_id`
- `mode`
- `status`
- `range_start`
- `range_end`
- `bytes_from_agent`
- `bytes_to_viewer`
- `created_at`
- `expires_at`

### 6.6 `hls_cache_entries`

字段：

- `cache_key`
- `project_id`
- `instance_id`
- `agent_id`
- `profile`
- `segment_name`
- `file_path`
- `size_bytes`
- `created_at`
- `last_accessed_at`
- `expires_at`

## 7. API 设计

### 7.1 Web 侧接口

#### `POST /api/desktop-agents/pairing-codes`

用途：

- 登录用户生成一次性配对码。

响应：

```json
{
  "ok": true,
  "data": {
    "pairingCode": "ABCD-EFGH",
    "expiresAt": "2026-03-10T12:00:00Z"
  }
}
```

#### `GET /api/desktop-agents`

用途：

- 列出当前账号下的连接器及在线状态。

#### `GET /api/projects/{projectId}/material-source-binding`

用途：

- 获取项目当前绑定的材料源。

#### `POST /api/projects/{projectId}/material-source-binding`

请求：

```json
{
  "sourceKind": "DESKTOP_AGENT_MANIFEST",
  "desktopAgentId": "agent_123",
  "sourceRootLabel": "Videos"
}
```

语义：

- 只切绑定，不隐式同步。

#### `GET /api/projects/{projectId}/media/instances/{instanceId}/playback`

用途：

- 返回播放描述符，而不是直接回视频字节。

#### `GET /api/projects/{projectId}/desktop-agents/status`

用途：

- 给项目设置页显示“已绑定设备 / 在线 / 上次同步时间 / 根目录标签”。

### 7.2 连接器侧接口

#### `POST /api/desktop-agents/pair`

请求：

```json
{
  "pairingCode": "ABCD-EFGH",
  "deviceName": "BYLOU-PC",
  "platform": "windows",
  "appVersion": "0.1.0"
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "agentId": "agent_123",
    "agentToken": "opaque-token",
    "refreshToken": "opaque-refresh-token",
    "serverTime": "2026-03-10T12:00:00Z"
  }
}
```

#### `POST /api/desktop-agents/manifest-sync`

请求：

```json
{
  "projectId": "proj_123",
  "agentId": "agent_123",
  "rootTitle": "Videos",
  "entries": [
    {
      "relativePath": "course-1/lesson-01.mp4",
      "sizeBytes": 123456789,
      "modifiedAt": "2026-03-10T10:00:00Z"
    }
  ]
}
```

语义：

- 先校验该 agent 是否被绑定到该项目。
- 服务端内部调用 `sync_learning_objects_from_manifest(...)`。

#### `PUT /api/desktop-agents/stream-sessions/{streamId}/chunks`

请求头：

- `Authorization: Bearer <agent_token>`
- `X-Chunk-Index`
- `X-Chunk-Offset`
- `X-Is-Final`

语义：

- 连接器向服务端回推 progressive 数据块。
- 服务端把块写入内存环形缓冲区，供浏览器 HTTP 响应消费。

#### `PUT /api/desktop-agents/hls-jobs/{jobId}/artifacts/{artifactPath}`

语义：

- 连接器上传 `master.m3u8`、`index.m3u8` 和各个 segment。
- 服务端写入缓存目录并更新索引。

## 8. WebSocket 协议

URL：

- `WS /api/desktop-agents/ws`

鉴权：

- `Authorization: Bearer <agent_token>`

### 8.1 连接器 -> 服务器

#### `hello`

```json
{
  "type": "hello",
  "agentId": "agent_123",
  "deviceName": "BYLOU-PC",
  "appVersion": "0.1.0"
}
```

#### `heartbeat`

```json
{
  "type": "heartbeat",
  "at": "2026-03-10T12:00:00Z",
  "bindings": [
    {
      "projectId": "proj_123",
      "rootTitle": "Videos"
    }
  ]
}
```

#### `job.state`

```json
{
  "type": "job.state",
  "jobId": "job_123",
  "state": "RUNNING"
}
```

### 8.2 服务器 -> 连接器

#### `probe.request`

```json
{
  "type": "probe.request",
  "requestId": "probe_123",
  "projectId": "proj_123",
  "instanceId": "inst_123",
  "relativePath": "course-1/lesson-01.mp4"
}
```

#### `stream.open`

```json
{
  "type": "stream.open",
  "streamId": "ms_123",
  "projectId": "proj_123",
  "instanceId": "inst_123",
  "relativePath": "course-1/lesson-01.mp4",
  "rangeStart": 0,
  "rangeEnd": 1048575,
  "contentType": "video/mp4"
}
```

#### `hls.start`

```json
{
  "type": "hls.start",
  "jobId": "job_456",
  "projectId": "proj_123",
  "instanceId": "inst_123",
  "relativePath": "course-1/lesson-01.mkv",
  "profile": {
    "heightMax": 720,
    "videoBitrate": "1800k",
    "audioBitrate": "128k",
    "segmentSeconds": 6
  }
}
```

#### `job.cancel`

```json
{
  "type": "job.cancel",
  "jobId": "job_456"
}
```

## 9. 缓存策略

### 9.1 Progressive

- 不落磁盘长缓存。
- 只做内存流式中继。
- 单个 `streamId` 维护环形缓冲区。
- 浏览器断开后立即取消 agent 任务。

### 9.2 HLS

- 所有产物落服务器磁盘缓存。
- 缓存键：

```text
(project_id, instance_id, manifest_generation, profile, segment_name)
```

- 命中缓存时，不再通知 agent。
- 清理策略：
  - LRU
  - 超过 `PLM_AGENT_CACHE_MAX_BYTES` 触发淘汰
  - 超过 `PLM_AGENT_CACHE_TTL_SECONDS` 过期

## 10. 安全约束

- 浏览器视频接口继续走现有登录 cookie 和项目权限校验。
- 连接器与浏览器令牌分离。
- 连接器只允许访问：
  - 自己账号下的 agent 资源
  - 自己被绑定到的项目
  - 自己上次选择目录下的相对路径
- 服务器必须拒绝：
  - 绝对路径
  - `..`
  - Windows 盘符路径
  - manifest 注入的重复/冲突路径
- 连接器本地必须拒绝：
  - 目录外逃逸
  - 软链接/快捷方式穿透

## 11. 仓库内改造清单

### 11.1 后端模型与持久化

新增：

- `backend/models/project_material_source_binding.py`
- `backend/models/desktop_agent.py`
- `backend/models/desktop_agent_pairing_code.py`
- `backend/models/media_stream_session.py`

修改：

- `backend/models/enums.py`
  - 新增 `MaterialSourceKind`
  - 新增审计事件枚举
- `backend/system/api.py`
  - 新增材料源绑定接口
  - 新增 manifest 同步接口
  - 新增 playback descriptor 接口
- `backend/system/runtime_features.py`
  - 新增 `desktop_agent_relay_enabled`
- SQL/JSON 持久层
  - 为新对象补读写

### 11.2 HTTP 适配层

新增：

- `adapter/routers/desktop_agents.py`

修改：

- `adapter/routers/projects.py`
  - 增加材料源绑定读写接口
- `adapter/routers/media.py`
  - 增加 playback descriptor
  - 增加 `/api/media/streams/{streamId}/...`
- `adapter/routers/system.py`
  - 暴露 `desktopAgentRelayEnabled`
- `adapter/schemas.py`
  - 增加配对、绑定、manifest、playback DTO

### 11.3 前端

修改：

- `frontend/src/views/settings/ProjectSettingsPage.tsx`
  - 新增下载连接器、生成配对码、设备选择、绑定状态、最后同步时间
- `frontend/src/views/workbench/components/VideoPane.tsx`
  - 改为先取 playback descriptor
  - HLS 模式接 `hls.js`
- `frontend/src/ui/api/system.ts`
  - 增加 `desktopAgentRelayEnabled`
- `frontend/src/ui/api/projects.ts`
  - 增加材料源绑定接口
- `frontend/src/ui/api/media.ts`
  - 增加 playback descriptor 接口

新增：

- `frontend/src/ui/api/desktopAgents.ts`
- `frontend/src/ui/queries/desktopAgents.ts`

### 11.4 连接器

新增顶层目录：

```text
desktop_agent/
  main.py
  service.py
  config_store.py
  manifest_scan.py
  relay_client.py
  probe.py
  transcode.py
  ui.py
```

建议实现：

- `service.py`
  - 进程主循环
  - token 刷新
  - WS 重连
- `manifest_scan.py`
  - 扫描媒体文件
  - 过滤隐藏项、软链接、快捷方式
- `probe.py`
  - 调用 `ffprobe`
- `transcode.py`
  - 调用 `ffmpeg`
- `ui.py`
  - 最小配置窗口
  - 目录选择
  - 配对状态

打包脚本：

- `tools/build_windows_desktop_agent.py`
- `tools/build_windows_desktop_agent_installer.py`

## 12. 分阶段实施

### Phase 1: 控制面闭环

交付：

- `ProjectMaterialSourceBinding`
- 配对码
- agent 注册/在线状态
- 项目绑定
- manifest 同步

验收：

- 用户能在网页看到连接器在线。
- 用户能把项目切到 `DESKTOP_AGENT_MANIFEST`。
- manifest 同步后，项目实例和学习对象树可见。

### Phase 2: Progressive relay

交付：

- playback descriptor
- `relay_progressive`
- Range 中继
- 运行时可达性校验

验收：

- `mp4` 可在其他设备播放。
- 快进和拖动进度条可用。
- 连接器离线时，播放器得到明确错误。

### Phase 3: Local transcode + HLS

交付：

- `probe`
- `relay_hls`
- 服务器分片缓存
- HLS 播放

验收：

- `mkv/hevc` 可播放。
- 同一视频二次播放不重复转码。
- agent 上行明显低于源文件原码率。

### Phase 4: 产品化

交付：

- 开机自启
- 托盘
- 自动更新
- 流量/并发限制
- 管理员监控页

## 13. 先实现什么

建议按以下顺序落代码：

1. 先把 `spec` 对应的新模型和白名单入口补进后端。
2. 再做项目设置页的“配对 + 绑定 + 在线状态”。
3. 之后实现 `sync_learning_objects_from_manifest(...)` 的后端闭环。
4. 然后上 `relay_progressive`。
5. 最后再补 `ffprobe/ffmpeg + HLS`。

这样做的原因：

- Phase 1 就能验证“公网版 + 本机目录 + 同账号项目绑定”的核心产品价值。
- Progressive relay 能最快跑通首个可播放路径。
- HLS 压缩是成本优化，不应阻塞架构闭环。

## 14. 截至 2026-03-11 的仓库实现状态

这一节描述“代码库当前已经实现到哪里”，避免把目标态和现状混为一谈。

### 14.1 已落地

- 后端模型已存在：
  - `DesktopAgent`
  - `DesktopAgentPairingCode`
  - `ProjectMaterialSourceBinding`
  - `DesktopMediaProbeCache`
  - `MediaStreamSession`
  - `HlsCacheEntry`
- 持久化已打通：
  - `auth_store.py` 已保存 agent、pairing code、在线状态。
  - `auth_store.py` / SQLite / PostgreSQL 已补上 probe cache、stream session、HLS cache 相关表与读写。
- Web 侧接口已打通：
  - `POST /api/desktop-agents/pairing-codes`
  - `GET /api/desktop-agents`
  - `POST /api/desktop-agents/pair`
  - `POST /api/desktop-agents/refresh-token`
  - `POST /api/desktop-agents/manifest-sync`
  - `WS /api/desktop-agents/ws`
  - `GET /api/projects/{projectId}/material-source-binding`
  - `POST /api/projects/{projectId}/material-source-binding`
  - `GET /api/projects/{projectId}/desktop-agents/status`
  - `GET /api/projects/{projectId}/media/instances/{instanceId}/playback`
  - `GET /api/projects/{projectId}/media/instances/{instanceId}/relay-file`
  - `PUT /api/desktop-agents/stream-sessions/{streamId}/chunks`
  - `PUT /api/desktop-agents/hls-jobs/{jobId}/artifacts/{artifactPath}`
  - `GET /api/media/streams/{streamId}/{artifactPath}`
  - `GET /api/system/runtime` 已暴露 relay runtime 指标与 HLS cache 统计，且在启用 auth 的 hosted 模式下不再匿名开放
  - `GET /api/system/desktop-agent-release` / `GET /api/system/desktop-agent-release/assets/{filename}` 已暴露连接器发布元数据与下载入口
- WS 控制面已打通：
  - `hello`
  - `heartbeat`
  - `probe.request` / `probe.result`
  - `stream.open`
  - `stream.cancel`
  - `hls.start`
  - `job.cancel`
  - `job.state`
- 前端已接入：
  - 项目设置页可生成配对码、列出已配对设备、绑定设备到项目、显示在线状态。
  - 项目设置页可直接查看最新连接器版本并下载安装包。
  - `VideoPane` 已先取 playback descriptor。
  - `relay_progressive` 直接走服务端 relay URL。
  - `relay_hls` 已支持原生 HLS 或 `hls.js` 播放，并轮询等待转码完成。
- 连接器已具备基础产品形态：
  - `desktop_agent/main.py` 提供 `pair` / `sync` / `run` / `ui` / `tray` 命令。
  - `service.py` 已实现 token 刷新、WS 重连、计划性轮换。
  - `tray.py` / `ui.py` / `autostart.py` 已提供托盘、图形配置窗口、开机自启。
  - `tray.py` / `ui.py` 已支持检查最新版本、下载发布包和触发静默安装；`tray.py` 也可按环境变量自动静默更新。
  - `relay_client.py` 可响应 `probe.request`、`stream.open`、`hls.start`。
  - `manifest_scan.py` 会过滤隐藏项，并拒绝软链接、快捷方式。
  - 本地路径解析已拒绝 `..`、盘符路径、软链接和 `.lnk` 快捷方式。
  - `tools/build_windows_desktop_agent_installer.py` 已可生成 installer bundle、release manifest，并可选接入 `signtool` 签名。
- 自动化测试已覆盖：
  - 配对
  - 项目绑定
  - manifest 同步
  - 在线状态更新
  - probe 与播放决策
  - progressive relay 往返播放
  - HLS artifact round-trip 与缓存清理
  - service / tray / UI / 本地路径安全

### 14.2 当前实现的边界

- 当前 playback decision 已有 probe + cache + `progressive/hls` 分流，但仍是首版规则：
  - 只按容器、视频编码、音频编码、码率做判断。
  - 还没有浏览器能力矩阵、多码率、自适应 profile。
- 当前 progressive relay 已具备持久化与超时/并发控制，但仍是简化版：
  - 仅支持单个 HTTP Range 请求。
  - 已能下发显式 `stream.cancel`，但 agent 侧取消仍是“尽快停止”而非硬实时中断。
  - 不支持 suffix range 和多段 range。
  - Relay Monitor 现在已能看到流量汇总、stream/HLS 原因分布、HLS cache 命中率、janitor 回收分布，以及基于后台采样的近 6 小时 / 24 小时趋势。
- 当前 manifest 扫描是“按扩展名发现文件”：
  - 目录树扫描和播放前 probe 已分离。
  - manifest 已带 `displayName` / `mediaKind` / ISO `modifiedAt`，服务端同步时会保留 `displayName` 作为学习对象标题。
  - 当 manifest 上报的 `modifiedAt/sizeBytes` 与已有 probe cache 不一致时，服务端会失效该实例的 probe cache 与 HLS cache，并取消仍在运行的旧 HLS job，避免原路径文件被替换后继续命中陈旧缓存。
  - probe cache 已额外持久化 `fps`、声道数、采样率、流数量、文件大小和 `modifiedAt`，播放 descriptor 也会带出 probe 摘要与决策原因。
  - 已补上基础浏览器能力矩阵：会按 Safari / Chromium / Firefox / Edge / generic 区分 progressive 可播容器与 codec，并把浏览器相关的决策原因带回前端。
  - 还没有更完整的设备能力探测、多 profile 和 ABR / 低延迟 HLS。
- 当前 HLS 已打通，但仍是单档缓存版：
  - 只有单 profile HLS，没有 ABR 和低延迟模式。
  - FastAPI lifespan 已起独立后台 janitor，定时回收过期 stream / probe / HLS job 并清理 HLS cache；`/api/system/runtime` 仍会复用同一套 maintenance pass 做即时采样。
  - HLS job 审计现已落到 auth store，可保留状态、artifact 统计和终态时间；但还没有更细粒度的事件流或恢复队列表。
- 当前连接器已经不是纯 CLI，但产品化还没收尾：
  - 已有下载入口、installer bundle、release manifest、sha256 校验、签名状态元数据，以及 tray/UI/启动时自动静默更新。
  - 构建脚本已支持可选 `signtool` 签名，客户端也可配置为仅接受 `SIGNED` 发布包。
  - 静默更新 helper 现已带安装前备份、post-install `healthcheck`、失败自动回滚，以及本地更新日志 / 回滚脚本。
  - 服务端发布入口现已可启用 signed-only policy，未满足签名策略的安装包不会出现在 release API 和下载接口里。
  - 还没有增量更新、多版本回滚槽位，以及更强的发布前检查和签名发布约束。
  - 已有 Relay Monitor 页面、持久化 HLS 审计、后台采样趋势、agent 结构化诊断回传、当前告警摘要、按 24 小时 / 72 小时 / 7 天筛选的诊断检索与 JSONL 导出，以及基于 janitor 的外部 alert webhook。
  - Relay Monitor 的趋势现已包含近 6 小时 / 24 小时明细，以及近 7 天 / 30 天聚合视图，并暴露 metric sample retention 与历史覆盖起点。
  - alert webhook 现已支持多通道投递、失败退避重试、内建 `log` sink 和每通道状态可见；但还没有更长时间尺度的历史报表，以及更完整的外部多通道类型（如邮件/IM）集成。

## 15. 目标态与当前实现的主要差异

### 15.1 播放决策层

- 目标态：
  - 先 probe，再在 `direct / progressive / hls` 之间做决策。
- 当前态：
  - 已有 `direct_file`、`relay_progressive`、`relay_hls`。
  - 已按基础浏览器能力矩阵细化 progressive 决策，并会返回浏览器相关的 `decisionReason`。
  - 但 `relay_hls` 仍只有单档 profile，也还没有更完整的设备能力探测和多 profile 决策。

### 15.2 控制面协议

- 目标态：
  - WS 承载 `probe.request`、`stream.open`、`hls.start`、`job.cancel`、`job.state`。
- 当前态：
  - `hello`、`heartbeat`、`probe.request`、`stream.open`、`stream.cancel`、`hls.start`、`job.cancel`、`job.state` 已使用。
  - 服务端和 agent 两侧都已回传 / 生成 probe、relay、HLS 关键诊断事件，HLS job 审计也已持久化。
  - 仍缺更完整的任务恢复、重试和更细粒度的事件级审计。

### 15.3 数据面

- 目标态：
  - progressive 走流式区间上传。
  - HLS 走 artifact 上传和服务器缓存。
- 当前态：
  - progressive 流式区间上传已可用，并记录 session 字节数与终态。
  - HLS artifact 上传、服务器缓存和浏览器拉取都已可用。
  - 已有后台 cache janitor、cache 命中率、artifact 请求量、回收原因分布、持久化 HLS job 审计、relay metric sample 驱动的近 6 小时 / 24 小时明细与近 7 天 / 30 天聚合趋势，以及 agent 诊断事件回传、当前告警摘要、长窗口诊断查询、JSONL 导出和外部 alert webhook。
  - alert webhook 已支持多通道投递、退避重试和内建 `log` sink；但还缺更长时间尺度的历史报表、更多外部告警通道类型和更强的中断恢复。

### 15.4 连接器产品化

- 目标态：
  - Windows 常驻程序，具备 UI、托盘、自启、自动更新、目录安全控制。
- 当前态：
  - UI、托盘、自启、refresh token 刷新、目录安全控制都已落地。
  - Relay Monitor 已可看设备状态、最近 stream issue、持久化 HLS job、cache 命中率、近 6 小时 / 24 小时明细、近 7 天 / 30 天聚合趋势、agent 诊断事件、当前告警摘要、带筛选的诊断检索与导出，以及带每通道状态的 alert webhook 发送/重试情况。
  - 下载分发入口、installer bundle、release manifest、UI/tray 更新检查、sha256 下载校验、静默安装和可选签名安装器都已落地。
  - 静默更新现已附带本地更新状态持久化、post-install `healthcheck`、失败自动回滚，以及 tray/UI 的更新日志 / 回滚入口。
  - 服务端现已可启用 signed-only release policy；仍缺增量更新、多版本回滚、更强的发布前签名校验，以及更长时间尺度的历史报表。

## 16. 建议按 PR 切分的下一轮开发

### PR-1：补强运维审计与监控

目标：

- 让现有 Relay Monitor 从“基础可见”提升到更适合排障和运维。

建议内容：

- 把已落地的持久化 HLS job 审计和 relay metric sample 继续扩展成更长时间窗口的运维报表，并视需要补更长 retention 或分层采样。
- 若需要，再把 cache 命中率、回收原因分布继续细化成更完整的趋势面板。
- 在已落地的 agent 诊断回传、当前告警摘要、长窗口检索、导出接口，以及支持多通道和重试的 webhook 基础上，继续补长期 retention、历史报表和更多告警通道类型。

完成标志：

- 管理侧能区分超时、断线、viewer 取消、转码失败等主要故障类型。
- 运行时指标不只看当前值，也能看最近一段时间的变化，并支持持久化审计与趋势采样。

### PR-2：补强媒体元数据与本地安全

目标：

- 让扫描、probe、播放决策和本地目录安全都更接近产品可用状态。

当前状态：

- 已落地 manifest ISO `modifiedAt`、`displayName`、`mediaKind`。
- 已落地 richer probe 元数据：
  - `fps`
  - `audioChannels`
  - `audioSampleRate`
  - `video/audio/subtitle stream count`
  - `sizeBytes`
  - `modifiedAt`
- 已落地本地工具自检与失败诊断：
  - `ffprobe_missing`
  - `ffmpeg_missing`
  - `probe_failed` 会带文件 stat 与工具路径上下文
- 目录安全方面已经拒绝软链接、快捷方式和上级逃逸；若后续要继续补，只剩更细的 Windows reparse point / junction 边角校验。

剩余可选增强：

- 继续把浏览器能力矩阵细化到更完整的设备 / 封装 / codec 组合。
- 继续细化 direct / progressive / hls 决策阈值与 profile 选择。
- 视需要把 richer probe/manifest 元数据直接接到更多前端排障视图。

### PR-3：把更新链路补到更接近产品级

目标：

- 从“可下载安装和检查更新”提升到“更接近真实产品发布流程”。

建议内容：

- 在现有 release manifest、sha256 校验、静默安装和可选签名基础上，继续补 changelog 展示、升级失败诊断和更清晰的回滚指引。
- 若要进一步产品化，再补增量更新、多版本回滚和更强的发布前签名校验。
- 视需要把现在已经落地的 signed-only policy 从运行时过滤扩展到构建 / 发布流程校验。

完成标志：

- 升级链路不只可用，而且失败时有明确诊断和回滚边界。

### PR-4：继续补强 Windows 连接器发布安全性

目标：

- 从“已可下载安装和检查更新”继续提升到更可信的产品发布流程。

建议内容：

- 为发布流程增加更强的签名约束、构建校验和发布前检查。
- 若要继续产品化，再补增量更新、多版本回滚和更完善的升级失败恢复。
- 为版本发布页补 changelog、回滚指引和更清晰的升级诊断。

完成标志：

- 发布流程更可信，用户能明确知道如何升级、失败后如何恢复，以及哪些发布包可被自动接受。

## 17. 最小验收测试清单

在后续每个阶段合并前，至少应保留下面这些回归用例。

### 17.1 控制面

- 用户 A 不能绑定用户 B 的 agent。
- 已过期配对码不能重复使用。
- agent 建立 WS 后，项目状态页能看到 `ONLINE`。
- WS 断开后，状态自动回落到 `OFFLINE`。

### 17.2 Manifest 同步

- 空目录或无视频目录不会破坏现有项目结构。
- 非法相对路径会被拒绝：
  - 绝对路径
  - `..`
  - 盘符路径
- 同一 manifest 重复同步时返回 `unchanged=true`。

### 17.3 Progressive relay

- 浏览器发 `Range: bytes=0-3` 时返回 `206` 和正确 `Content-Range`。
- agent 上传多块数据时，浏览器按顺序收到完整字节流。
- 浏览器中途断开时，服务端能释放 `streamId`。
- agent 离线时，descriptor 或 relay 请求返回明确错误而不是挂死。

### 17.4 HLS relay

- 首次播放会触发本地转码并生成缓存。
- 二次播放命中缓存，不再再次转码。
- 缓存过期或超限后，旧 segment 会被清理。
- 非兼容编码文件能稳定回落到 `relay_hls`。

## 18. 现在最值得先做的事

如果只考虑“最快获得真实用户价值”，优先级建议改成：

1. 先把运维侧继续补到更长 retention、更多告警通道和历史报表。
2. 再把更新链路继续补到增量更新、多版本回滚和更强签名约束。
3. 最后再把浏览器能力矩阵继续细化到更复杂的播放决策。

原因：

- 现在仓库已经有 hosted + agent + manifest sync + richer probe + progressive + HLS + tray/UI + release manifest + sha256 校验 + 静默更新的完整闭环，主链路已经成立。
- 运维面现在已经有 runtime、趋势、告警和诊断导出，继续做主要是“更久、更稳、更全”，这是下一阶段最直接的日常运维价值。
- 更新链路已经可用，下一步更偏“产品级安全与恢复能力”的补强，而不是闭环缺口。
- 播放策略的下一步更多是精细化优化，而不是当前闭环成立的前提条件。
