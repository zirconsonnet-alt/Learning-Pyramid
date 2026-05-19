use std::{
    collections::HashMap,
    fs::{self, File},
    io::{Read, Seek, SeekFrom},
    net::{SocketAddr, TcpListener},
    path::{Component, Path, PathBuf},
    sync::{Arc, Mutex},
    thread,
};

use reqwest::blocking::Client;
use reqwest::header::{CONTENT_LENGTH, CONTENT_RANGE, CONTENT_TYPE, RANGE};
use tiny_http::{Header, Method, Request, Response, Server, StatusCode};

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopHealth {
    ok: bool,
    runtime: &'static str,
    platform: &'static str,
    arch: &'static str,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct NativeMediaPlayback {
    url: String,
    mime_type: String,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct BaiduHlsPlayback {
    url: String,
    mime_type: String,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct NativeLocalDirectoryScan {
    project_root: String,
    root_title: String,
    relative_file_paths: Vec<String>,
}

#[derive(serde::Serialize)]
#[serde(untagged)]
enum NativeSubtitleFile {
    Found(NativeSubtitleFound),
    Missing(NativeSubtitleMissing),
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct NativeSubtitleFound {
    found: bool,
    file_name: String,
    format: String,
    text: String,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct NativeSubtitleMissing {
    found: bool,
}

#[derive(Clone, Eq, PartialEq)]
struct MediaEntry {
    path: PathBuf,
    mime_type: String,
}

struct NativeMediaServer {
    addr: SocketAddr,
    entries: Arc<Mutex<HashMap<String, MediaEntry>>>,
    baidu_hls_entries: Arc<Mutex<HashMap<String, BaiduHlsEntry>>>,
}

#[derive(Default)]
struct NativeMediaState {
    server: Mutex<Option<NativeMediaServer>>,
}

#[derive(Clone, Eq, PartialEq)]
struct BaiduHlsEntry {
    playlist_text: String,
    upstream_url: String,
}

#[tauri::command]
fn desktop_health() -> DesktopHealth {
    DesktopHealth {
        ok: true,
        runtime: "desktop",
        platform: std::env::consts::OS,
        arch: std::env::consts::ARCH,
    }
}

#[tauri::command]
fn desktop_choose_local_directory() -> Result<Option<NativeLocalDirectoryScan>, String> {
    let Some(selected) = rfd::FileDialog::new()
        .set_title("选择本地视频文件夹")
        .pick_folder()
    else {
        return Ok(None);
    };
    let root = selected
        .canonicalize()
        .map_err(|err| format!("本地文件夹不可访问: {err}"))?;
    if !root.is_dir() {
        return Err("选择的路径不是文件夹".to_string());
    }
    if root.is_symlink() {
        return Err("暂不支持选择符号链接文件夹".to_string());
    }
    let root_title = root
        .file_name()
        .map(|value| value.to_string_lossy().to_string())
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| root.to_string_lossy().to_string());
    let relative_file_paths = scan_native_local_media_files(&root)?;
    Ok(Some(NativeLocalDirectoryScan {
        project_root: root.to_string_lossy().to_string(),
        root_title,
        relative_file_paths,
    }))
}

#[tauri::command]
fn desktop_native_media_url(
    state: tauri::State<'_, NativeMediaState>,
    project_root: String,
    learning_object_root: String,
    material_id: String,
) -> Result<NativeMediaPlayback, String> {
    let material_path =
        resolve_native_material_path(&project_root, &learning_object_root, &material_id)?;
    let mime_type = mime_type_for_path(&material_path);
    let entry = MediaEntry {
        path: material_path,
        mime_type: mime_type.clone(),
    };
    let token = state.register(entry)?;
    let addr = state.server_addr()?;
    Ok(NativeMediaPlayback {
        url: format!("http://{addr}/media/{token}"),
        mime_type,
    })
}

#[tauri::command]
fn desktop_native_subtitle_file(
    project_root: String,
    learning_object_root: String,
    material_id: String,
) -> Result<NativeSubtitleFile, String> {
    let material_path =
        resolve_native_material_path(&project_root, &learning_object_root, &material_id)?;
    let Some(subtitle_path) = find_sibling_subtitle_path(&material_path)? else {
        return Ok(NativeSubtitleFile::Missing(NativeSubtitleMissing {
            found: false,
        }));
    };
    let format = subtitle_format_for_path(&subtitle_path)
        .ok_or_else(|| "暂不支持的字幕格式".to_string())?
        .to_string();
    let text = fs::read_to_string(&subtitle_path)
        .map_err(|err| format!("读取本地字幕文件失败: {err}"))?
        .trim_start_matches('\u{feff}')
        .to_string();
    let file_name = subtitle_path
        .file_name()
        .map(|value| value.to_string_lossy().to_string())
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| "本地字幕文件名不可用".to_string())?;
    Ok(NativeSubtitleFile::Found(NativeSubtitleFound {
        found: true,
        file_name,
        format,
        text,
    }))
}

#[tauri::command]
fn desktop_baidu_hls_url(
    state: tauri::State<'_, NativeMediaState>,
    playlist_text: String,
    upstream_url: String,
) -> Result<BaiduHlsPlayback, String> {
    let normalized_upstream_url = normalize_baidu_upstream_url(&upstream_url)?;
    let normalized_playlist =
        normalize_baidu_hls_playlist(&playlist_text, &normalized_upstream_url)?;
    let token = state.register_baidu_hls(BaiduHlsEntry {
        playlist_text: normalized_playlist,
        upstream_url: normalized_upstream_url,
    })?;
    let addr = state.server_addr()?;
    Ok(BaiduHlsPlayback {
        url: format!("http://{addr}/baidu-hls/{token}/playlist.m3u8"),
        mime_type: "application/vnd.apple.mpegurl".to_string(),
    })
}

impl NativeMediaState {
    fn register(&self, entry: MediaEntry) -> Result<String, String> {
        self.ensure_server()?;
        let token = uuid::Uuid::new_v4().simple().to_string();
        let guard = self
            .server
            .lock()
            .map_err(|_| "本地媒体服务状态不可用".to_string())?;
        let server = guard
            .as_ref()
            .ok_or_else(|| "本地媒体服务不可用".to_string())?;
        let mut entries = server
            .entries
            .lock()
            .map_err(|_| "本地媒体服务索引不可用".to_string())?;
        if let Some(existing_token) = entries.iter().find_map(|(existing_token, existing)| {
            if existing == &entry {
                Some(existing_token.clone())
            } else {
                None
            }
        }) {
            return Ok(existing_token);
        }
        entries.insert(token.clone(), entry);
        Ok(token)
    }

    fn register_baidu_hls(&self, entry: BaiduHlsEntry) -> Result<String, String> {
        self.ensure_server()?;
        let token = uuid::Uuid::new_v4().simple().to_string();
        let guard = self
            .server
            .lock()
            .map_err(|_| "本地媒体服务状态不可用".to_string())?;
        let server = guard
            .as_ref()
            .ok_or_else(|| "本地媒体服务不可用".to_string())?;
        let mut entries = server
            .baidu_hls_entries
            .lock()
            .map_err(|_| "百度网盘播放索引不可用".to_string())?;
        if let Some(existing_token) = entries.iter().find_map(|(existing_token, existing)| {
            if existing == &entry {
                Some(existing_token.clone())
            } else {
                None
            }
        }) {
            return Ok(existing_token);
        }
        entries.insert(token.clone(), entry);
        Ok(token)
    }

    fn server_addr(&self) -> Result<SocketAddr, String> {
        self.ensure_server()?;
        let guard = self
            .server
            .lock()
            .map_err(|_| "本地媒体服务状态不可用".to_string())?;
        guard
            .as_ref()
            .map(|server| server.addr)
            .ok_or_else(|| "本地媒体服务不可用".to_string())
    }

    fn ensure_server(&self) -> Result<(), String> {
        let mut guard = self
            .server
            .lock()
            .map_err(|_| "本地媒体服务状态不可用".to_string())?;
        if guard.is_some() {
            return Ok(());
        }

        let listener = TcpListener::bind("127.0.0.1:0")
            .map_err(|err| format!("启动本地媒体服务失败: {err}"))?;
        let addr = listener
            .local_addr()
            .map_err(|err| format!("读取本地媒体服务地址失败: {err}"))?;
        let entries = Arc::new(Mutex::new(HashMap::new()));
        let baidu_hls_entries = Arc::new(Mutex::new(HashMap::new()));
        let http_client = Client::builder()
            .redirect(reqwest::redirect::Policy::limited(10))
            .build()
            .map_err(|err| format!("初始化本地网络客户端失败: {err}"))?;
        let server = Server::from_listener(listener, None)
            .map_err(|err| format!("初始化本地媒体服务失败: {err}"))?;
        let worker_entries = Arc::clone(&entries);
        let worker_baidu_hls_entries = Arc::clone(&baidu_hls_entries);
        let worker_http_client = http_client.clone();

        thread::Builder::new()
            .name("learningpyramid-native-media".to_string())
            .spawn(move || {
                for request in server.incoming_requests() {
                    handle_media_request(
                        request,
                        &worker_entries,
                        &worker_baidu_hls_entries,
                        &worker_http_client,
                    );
                }
            })
            .map_err(|err| format!("启动本地媒体服务线程失败: {err}"))?;

        *guard = Some(NativeMediaServer {
            addr,
            entries,
            baidu_hls_entries,
        });
        Ok(())
    }
}

fn handle_media_request(
    request: Request,
    entries: &Arc<Mutex<HashMap<String, MediaEntry>>>,
    baidu_hls_entries: &Arc<Mutex<HashMap<String, BaiduHlsEntry>>>,
    http_client: &Client,
) {
    if request.method() == &Method::Options {
        respond_options(request);
        return;
    }

    if request.method() != &Method::Get && request.method() != &Method::Head {
        respond_text(request, StatusCode(405), "method not allowed");
        return;
    }

    if request.url().starts_with("/baidu-hls/") {
        handle_baidu_hls_request(request, baidu_hls_entries, http_client);
        return;
    }

    let token = match request.url().strip_prefix("/media/") {
        Some(value) if !value.is_empty() && !value.contains('/') && !value.contains("..") => {
            value.to_string()
        }
        _ => {
            respond_text(request, StatusCode(404), "not found");
            return;
        }
    };

    let entry = match entries
        .lock()
        .ok()
        .and_then(|items| items.get(&token).cloned())
    {
        Some(value) => value,
        None => {
            respond_text(request, StatusCode(404), "not found");
            return;
        }
    };

    if !entry.path.is_file() {
        respond_text(request, StatusCode(404), "not found");
        return;
    }

    let metadata = match entry.path.metadata() {
        Ok(value) => value,
        Err(_) => {
            respond_text(request, StatusCode(404), "not found");
            return;
        }
    };
    let file_len = metadata.len();
    let range_header = request
        .headers()
        .iter()
        .find(|header| header.field.equiv("Range"))
        .map(|header| header.value.as_str().to_string());
    let range = match parse_range_header(range_header.as_deref(), file_len) {
        Ok(value) => value,
        Err(status) => {
            respond_text(request, status, "invalid range");
            return;
        }
    };
    let is_head = request.method() == &Method::Head;

    let mut headers = vec![
        response_header("Accept-Ranges", "bytes"),
        response_header("Content-Type", &entry.mime_type),
        response_header("Cache-Control", "no-store"),
        response_header("Access-Control-Allow-Origin", "*"),
        response_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS"),
        response_header("Access-Control-Allow-Headers", "Range"),
        response_header(
            "Access-Control-Expose-Headers",
            "Accept-Ranges, Content-Length, Content-Range",
        ),
    ];

    let status;
    let content_len;
    let start;
    if let Some((range_start, range_end)) = range {
        status = StatusCode(206);
        content_len = range_end - range_start + 1;
        start = range_start;
        headers.push(response_header(
            "Content-Range",
            &format!("bytes {range_start}-{range_end}/{file_len}"),
        ));
    } else {
        status = StatusCode(200);
        content_len = file_len;
        start = 0;
    }
    headers.push(response_header("Content-Length", &content_len.to_string()));

    if is_head {
        let mut response = Response::empty(status);
        for header in headers {
            response.add_header(header);
        }
        let _ = request.respond(response);
        return;
    }

    let mut file = match File::open(&entry.path) {
        Ok(value) => value,
        Err(_) => {
            respond_text(request, StatusCode(404), "not found");
            return;
        }
    };
    if file.seek(SeekFrom::Start(start)).is_err() {
        respond_text(request, StatusCode(500), "seek failed");
        return;
    }

    let reader = file.take(content_len);
    let mut response = Response::new(status, headers, reader, Some(content_len as usize), None);
    response.add_header(response_header("Connection", "keep-alive"));
    let _ = request.respond(response);
}

fn handle_baidu_hls_request(
    request: Request,
    entries: &Arc<Mutex<HashMap<String, BaiduHlsEntry>>>,
    http_client: &Client,
) {
    let path_and_query = request.url().to_string();
    let path = path_and_query
        .split_once('?')
        .map(|(path, _)| path)
        .unwrap_or(&path_and_query);
    let Some(rest) = path.strip_prefix("/baidu-hls/") else {
        respond_text(request, StatusCode(404), "not found");
        return;
    };
    let Some((token, tail)) = rest.split_once('/') else {
        respond_text(request, StatusCode(404), "not found");
        return;
    };
    if !is_safe_token(token) {
        respond_text(request, StatusCode(404), "not found");
        return;
    }

    let entry = match entries
        .lock()
        .ok()
        .and_then(|items| items.get(token).cloned())
    {
        Some(value) => value,
        None => {
            respond_text(request, StatusCode(404), "not found");
            return;
        }
    };

    if tail == "playlist.m3u8" {
        respond_baidu_playlist(request, token, &entry);
        return;
    }

    if tail != "segment" {
        respond_text(request, StatusCode(404), "not found");
        return;
    }
    let Some(upstream_url) =
        query_param(&path_and_query, "u").and_then(|value| percent_decode(&value))
    else {
        respond_text(request, StatusCode(400), "missing upstream url");
        return;
    };
    if !is_allowed_baidu_upstream_url(&upstream_url) {
        respond_text(request, StatusCode(400), "invalid upstream url");
        return;
    }
    respond_baidu_upstream(request, http_client, token, &upstream_url);
}

fn respond_baidu_playlist(request: Request, token: &str, entry: &BaiduHlsEntry) {
    let text =
        rewrite_baidu_playlist_for_local_proxy(token, &entry.playlist_text, &entry.upstream_url);
    let content_len = text.as_bytes().len();
    if request.method() == &Method::Head {
        let mut response = Response::empty(StatusCode(200));
        response.add_header(response_header(
            "Content-Type",
            "application/vnd.apple.mpegurl; charset=utf-8",
        ));
        response.add_header(response_header("Content-Length", &content_len.to_string()));
        add_local_proxy_headers(&mut response);
        let _ = request.respond(response);
        return;
    }
    let mut response = Response::from_string(text).with_status_code(StatusCode(200));
    response.add_header(response_header(
        "Content-Type",
        "application/vnd.apple.mpegurl; charset=utf-8",
    ));
    response.add_header(response_header("Content-Length", &content_len.to_string()));
    add_local_proxy_headers(&mut response);
    let _ = request.respond(response);
}

fn respond_baidu_upstream(request: Request, http_client: &Client, token: &str, upstream_url: &str) {
    let range_header = request
        .headers()
        .iter()
        .find(|header| header.field.equiv("Range"))
        .map(|header| header.value.as_str().to_string());
    let is_head = request.method() == &Method::Head;
    let mut upstream_request = http_client.get(upstream_url);
    if let Some(range) = range_header.as_deref() {
        upstream_request = upstream_request.header(RANGE, range);
    }
    let upstream_response = match upstream_request.send() {
        Ok(value) => value,
        Err(_) => {
            respond_text(request, StatusCode(502), "upstream request failed");
            return;
        }
    };
    let status_code = StatusCode(upstream_response.status().as_u16());
    if upstream_response.status().as_u16() >= 400 {
        respond_text(request, status_code, "upstream request failed");
        return;
    }

    let content_type = upstream_response
        .headers()
        .get(CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.trim().is_empty())
        .unwrap_or("application/octet-stream")
        .to_string();
    let upstream_final_url = upstream_response.url().to_string();
    let content_len = upstream_response
        .headers()
        .get(CONTENT_LENGTH)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.parse::<u64>().ok());
    let content_range = upstream_response
        .headers()
        .get(CONTENT_RANGE)
        .and_then(|value| value.to_str().ok())
        .map(|value| value.to_string());
    let mut headers = vec![
        response_header("Accept-Ranges", "bytes"),
        response_header("Content-Type", &content_type),
        response_header("Cache-Control", "no-store"),
        response_header("Access-Control-Allow-Origin", "*"),
        response_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS"),
        response_header("Access-Control-Allow-Headers", "Range"),
        response_header(
            "Access-Control-Expose-Headers",
            "Accept-Ranges, Content-Length, Content-Range",
        ),
    ];
    if let Some(value) = content_len {
        headers.push(response_header("Content-Length", &value.to_string()));
    }
    if let Some(value) = content_range {
        headers.push(response_header("Content-Range", &value));
    }

    if is_head {
        let mut response = Response::empty(status_code);
        for header in headers {
            response.add_header(header);
        }
        let _ = request.respond(response);
        return;
    }

    if is_hls_playlist_content_type(&content_type) {
        match upstream_response.text() {
            Ok(text) => {
                let rewritten =
                    rewrite_baidu_playlist_for_local_proxy(token, &text, &upstream_final_url);
                let mut playlist_headers = headers;
                playlist_headers.retain(|header| !header.field.equiv("Content-Length"));
                playlist_headers.push(response_header(
                    "Content-Length",
                    &rewritten.as_bytes().len().to_string(),
                ));
                let response = Response::new(
                    status_code,
                    playlist_headers,
                    std::io::Cursor::new(rewritten),
                    None,
                    None,
                );
                let _ = request.respond(response);
                return;
            }
            Err(_) => {
                respond_text(request, StatusCode(502), "upstream playlist read failed");
                return;
            }
        }
    }

    let response = Response::new(
        status_code,
        headers,
        upstream_response,
        content_len.and_then(|value| usize::try_from(value).ok()),
        None,
    );
    let _ = request.respond(response);
}

fn normalize_baidu_hls_playlist(text: &str, upstream_url: &str) -> Result<String, String> {
    let normalized = text.trim_start_matches('\u{feff}').trim().to_string();
    if !normalized.starts_with("#EXTM3U") {
        return Err("百度网盘播放列表内容无效".to_string());
    }
    for raw_line in normalized.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let target = resolve_baidu_hls_url(upstream_url, line)
            .ok_or_else(|| "百度网盘播放列表包含无法解析的分片地址".to_string())?;
        if !is_allowed_baidu_upstream_url(&target) {
            return Err("百度网盘播放列表包含不可访问的分片地址".to_string());
        }
    }
    Ok(normalized)
}

fn rewrite_baidu_playlist_for_local_proxy(token: &str, text: &str, upstream_url: &str) -> String {
    let mut lines = Vec::new();
    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            lines.push(raw_line.to_string());
            continue;
        }
        let Some(target) = resolve_baidu_hls_url(upstream_url, line) else {
            lines.push(raw_line.to_string());
            continue;
        };
        lines.push(format!(
            "/baidu-hls/{token}/segment?u={}",
            percent_encode(&target)
        ));
    }
    lines.join("\n") + "\n"
}

fn normalize_baidu_upstream_url(value: &str) -> Result<String, String> {
    let normalized = value.trim().to_string();
    if !is_allowed_baidu_upstream_url(&normalized) {
        return Err("百度网盘播放列表来源地址不可访问".to_string());
    }
    Ok(normalized)
}

fn resolve_baidu_hls_url(base_url: &str, value: &str) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return None;
    }
    if trimmed.starts_with("https://") {
        return Some(trimmed.to_string());
    }
    if trimmed.starts_with("//") {
        return Some(format!("https:{trimmed}"));
    }
    let (base_without_fragment, _) = base_url.split_once('#').unwrap_or((base_url, ""));
    let (base_without_query, _) = base_without_fragment
        .split_once('?')
        .unwrap_or((base_without_fragment, ""));
    let (scheme, rest) = base_without_query.split_once("://")?;
    let host = rest.split('/').next()?;
    if trimmed.starts_with('/') {
        return Some(format!("{scheme}://{host}{trimmed}"));
    }
    let base_dir = base_without_query
        .rsplit_once('/')
        .map(|(dir, _)| format!("{dir}/"))
        .unwrap_or_else(|| format!("{scheme}://{host}/"));
    Some(format!("{base_dir}{trimmed}"))
}

fn is_hls_playlist_content_type(value: &str) -> bool {
    let normalized = value
        .split(';')
        .next()
        .unwrap_or("")
        .trim()
        .to_ascii_lowercase();
    normalized == "application/vnd.apple.mpegurl"
        || normalized == "application/x-mpegurl"
        || normalized == "audio/mpegurl"
        || normalized == "audio/x-mpegurl"
}

fn is_safe_token(value: &str) -> bool {
    !value.is_empty()
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_')
}

fn query_param(url: &str, name: &str) -> Option<String> {
    let query = url.split_once('?')?.1;
    for pair in query.split('&') {
        let (key, value) = pair.split_once('=').unwrap_or((pair, ""));
        if key == name {
            return Some(value.to_string());
        }
    }
    None
}

fn is_allowed_baidu_upstream_url(value: &str) -> bool {
    let normalized = value.trim().to_ascii_lowercase();
    if !normalized.starts_with("https://") {
        return false;
    }
    let Some(host_start) = normalized.strip_prefix("https://") else {
        return false;
    };
    let host = host_start
        .split(['/', '?', '#'])
        .next()
        .unwrap_or("")
        .split('@')
        .last()
        .unwrap_or("")
        .split(':')
        .next()
        .unwrap_or("");
    host == "baidu.com"
        || host.ends_with(".baidu.com")
        || host == "baidupcs.com"
        || host.ends_with(".baidupcs.com")
        || host == "bdstatic.com"
        || host.ends_with(".bdstatic.com")
}

fn percent_encode(value: &str) -> String {
    let mut output = String::new();
    for byte in value.bytes() {
        if byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.' | b'~') {
            output.push(byte as char);
        } else {
            output.push_str(&format!("%{byte:02X}"));
        }
    }
    output
}

fn percent_decode(value: &str) -> Option<String> {
    let bytes = value.as_bytes();
    let mut output = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' {
            if index + 2 >= bytes.len() {
                return None;
            }
            let high = hex_value(bytes[index + 1])?;
            let low = hex_value(bytes[index + 2])?;
            output.push((high << 4) | low);
            index += 3;
            continue;
        }
        output.push(bytes[index]);
        index += 1;
    }
    String::from_utf8(output).ok()
}

fn hex_value(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

fn resolve_native_material_path(
    project_root: &str,
    learning_object_root: &str,
    material_id: &str,
) -> Result<PathBuf, String> {
    let root = normalize_existing_dir(project_root, "项目根目录")?;
    let relative_learning_root =
        normalize_relative_path(learning_object_root, "学习对象根目录", true)?;
    let relative_material = normalize_relative_path(material_id, "素材路径", false)?;
    let media_root = root.join(relative_learning_root);
    let candidate = media_root.join(relative_material);
    let resolved_root = media_root
        .canonicalize()
        .map_err(|err| format!("学习对象根目录不可访问: {err}"))?;
    let resolved_file = candidate
        .canonicalize()
        .map_err(|err| format!("本地素材文件不可访问: {err}"))?;
    if !resolved_file.starts_with(&resolved_root) {
        return Err("本地素材路径逃逸出学习对象根目录".to_string());
    }
    if !resolved_file.is_file() {
        return Err("本地素材不是文件".to_string());
    }
    Ok(resolved_file)
}

fn find_sibling_subtitle_path(material_path: &Path) -> Result<Option<PathBuf>, String> {
    let parent = material_path
        .parent()
        .ok_or_else(|| "本地素材文件没有可读取的父目录".to_string())?;
    let material_stem = material_path
        .file_stem()
        .map(|value| value.to_string_lossy().to_string().to_lowercase())
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| "本地素材文件名不可用".to_string())?;
    let mut best_match: Option<(usize, PathBuf)> = None;
    let entries = fs::read_dir(parent).map_err(|err| format!("读取本地素材目录失败: {err}"))?;

    for entry in entries {
        let path = entry
            .map_err(|err| format!("读取本地素材目录项失败: {err}"))?
            .path();
        if !path.is_file() {
            continue;
        }
        let resolved_path = path
            .canonicalize()
            .map_err(|err| format!("本地字幕文件不可访问: {err}"))?;
        if resolved_path.parent() != Some(parent) {
            continue;
        }
        let Some(preference) = subtitle_extension_preference(&path) else {
            continue;
        };
        let Some(stem) = path
            .file_stem()
            .map(|value| value.to_string_lossy().to_string().to_lowercase())
        else {
            continue;
        };
        if stem != material_stem {
            continue;
        }
        if best_match
            .as_ref()
            .map(|(current_preference, _)| preference < *current_preference)
            .unwrap_or(true)
        {
            best_match = Some((preference, resolved_path));
        }
    }

    Ok(best_match.map(|(_, path)| path))
}

fn subtitle_extension_preference(path: &Path) -> Option<usize> {
    match subtitle_format_for_path(path)? {
        "srt" => Some(0),
        "vtt" => Some(1),
        "ass" => Some(2),
        "ssa" => Some(3),
        _ => None,
    }
}

fn subtitle_format_for_path(path: &Path) -> Option<&'static str> {
    match path
        .extension()
        .and_then(|value| value.to_str())
        .map(|value| value.to_ascii_lowercase())
        .as_deref()
    {
        Some("srt") => Some("srt"),
        Some("vtt") => Some("vtt"),
        Some("ass") => Some("ass"),
        Some("ssa") => Some("ssa"),
        _ => None,
    }
}

fn normalize_existing_dir(value: &str, label: &str) -> Result<PathBuf, String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(format!("{label}不能为空"));
    }
    let resolved = PathBuf::from(trimmed)
        .canonicalize()
        .map_err(|err| format!("{label}不可访问: {err}"))?;
    if !resolved.is_dir() {
        return Err(format!("{label}不是目录"));
    }
    Ok(resolved)
}

fn normalize_relative_path(
    value: &str,
    label: &str,
    allow_current_dir: bool,
) -> Result<PathBuf, String> {
    let trimmed = value.trim().replace('\\', "/");
    if trimmed.is_empty() {
        return Err(format!("{label}不能为空"));
    }
    if allow_current_dir && trimmed == "." {
        return Ok(PathBuf::new());
    }
    let raw = Path::new(&trimmed);
    if raw.is_absolute() {
        return Err(format!("{label}必须是相对路径"));
    }
    let mut output = PathBuf::new();
    for component in raw.components() {
        match component {
            Component::Normal(part) => output.push(part),
            _ => return Err(format!("{label}不能包含 . 或 ..")),
        }
    }
    if output.as_os_str().is_empty() {
        return Err(format!("{label}不能为空"));
    }
    Ok(output)
}

fn scan_native_local_media_files(root: &Path) -> Result<Vec<String>, String> {
    let mut collected = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(current) = stack.pop() {
        let entries = fs::read_dir(&current).map_err(|err| format!("读取本地文件夹失败: {err}"))?;
        for entry in entries {
            let entry = entry.map_err(|err| format!("读取本地文件夹条目失败: {err}"))?;
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().to_string();
            if name.is_empty() || name.starts_with('.') {
                continue;
            }
            if path.is_symlink() {
                return Err(format!("暂不支持符号链接: {}", path.to_string_lossy()));
            }
            if name.to_ascii_lowercase().ends_with(".lnk") {
                return Err(format!("暂不支持快捷方式: {}", path.to_string_lossy()));
            }
            let file_type = entry
                .file_type()
                .map_err(|err| format!("读取本地文件类型失败: {err}"))?;
            if file_type.is_dir() {
                stack.push(path);
                continue;
            }
            if !file_type.is_file() {
                return Err(format!(
                    "暂不支持的本地文件夹条目: {}",
                    path.to_string_lossy()
                ));
            }
            if !is_importable_media_path(&path) {
                continue;
            }
            let rel = path
                .strip_prefix(root)
                .map_err(|_| "本地媒体路径逃逸出所选文件夹".to_string())?;
            collected.push(path_to_posix_string(rel)?);
        }
    }
    collected.sort();
    collected.dedup();
    if collected.is_empty() {
        return Err("选择的本地文件夹中没有找到可导入的媒体文件".to_string());
    }
    Ok(collected)
}

fn is_importable_media_path(path: &Path) -> bool {
    matches!(
        path.extension()
            .and_then(|value| value.to_str())
            .map(|value| value.to_ascii_lowercase())
            .as_deref(),
        Some("mp4")
            | Some("mov")
            | Some("mkv")
            | Some("webm")
            | Some("mp3")
            | Some("wav")
            | Some("m4a")
            | Some("aac")
            | Some("flac")
            | Some("ogg")
            | Some("opus")
    )
}

fn path_to_posix_string(path: &Path) -> Result<String, String> {
    let mut parts = Vec::new();
    for component in path.components() {
        match component {
            Component::Normal(part) => {
                let text = part.to_string_lossy().to_string();
                if text.is_empty()
                    || text == "."
                    || text == ".."
                    || text.contains('/')
                    || text.contains('\\')
                {
                    return Err("本地媒体相对路径不合法".to_string());
                }
                parts.push(text);
            }
            _ => return Err("本地媒体相对路径不合法".to_string()),
        }
    }
    if parts.is_empty() {
        return Err("本地媒体相对路径不能为空".to_string());
    }
    Ok(parts.join("/"))
}

fn parse_range_header(
    header: Option<&str>,
    file_len: u64,
) -> Result<Option<(u64, u64)>, StatusCode> {
    let Some(raw) = header else {
        return Ok(None);
    };
    let range_text = raw.trim();
    if !range_text.starts_with("bytes=") || range_text.contains(',') {
        return Err(StatusCode(416));
    }
    let bounds = &range_text[6..];
    let Some((start_raw, end_raw)) = bounds.split_once('-') else {
        return Err(StatusCode(416));
    };
    if file_len == 0 {
        return Err(StatusCode(416));
    }
    if start_raw.is_empty() {
        let suffix_len = end_raw.parse::<u64>().map_err(|_| StatusCode(416))?;
        if suffix_len == 0 {
            return Err(StatusCode(416));
        }
        let start = file_len.saturating_sub(suffix_len);
        return Ok(Some((start, file_len - 1)));
    }
    let start = start_raw.parse::<u64>().map_err(|_| StatusCode(416))?;
    let end = if end_raw.is_empty() {
        file_len - 1
    } else {
        end_raw.parse::<u64>().map_err(|_| StatusCode(416))?
    };
    if start >= file_len || end < start {
        return Err(StatusCode(416));
    }
    Ok(Some((start, end.min(file_len - 1))))
}

fn mime_type_for_path(path: &Path) -> String {
    match path
        .extension()
        .and_then(|value| value.to_str())
        .map(|value| value.to_ascii_lowercase())
        .as_deref()
    {
        Some("mp4") => "video/mp4",
        Some("m4v") => "video/mp4",
        Some("mov") => "video/quicktime",
        Some("webm") => "video/webm",
        Some("mkv") => "video/x-matroska",
        Some("mp3") => "audio/mpeg",
        Some("m4a") => "audio/mp4",
        Some("aac") => "audio/aac",
        Some("wav") => "audio/wav",
        Some("flac") => "audio/flac",
        Some("ogg") => "audio/ogg",
        Some("opus") => "audio/ogg",
        _ => "application/octet-stream",
    }
    .to_string()
}

fn response_header(name: &str, value: &str) -> Header {
    Header::from_bytes(name.as_bytes(), value.as_bytes())
        .expect("static response header must be valid")
}

fn add_local_proxy_headers<R: Read>(response: &mut Response<R>) {
    response.add_header(response_header("Cache-Control", "no-store"));
    response.add_header(response_header("Access-Control-Allow-Origin", "*"));
    response.add_header(response_header(
        "Access-Control-Allow-Methods",
        "GET, HEAD, OPTIONS",
    ));
    response.add_header(response_header("Access-Control-Allow-Headers", "Range"));
    response.add_header(response_header(
        "Access-Control-Expose-Headers",
        "Accept-Ranges, Content-Length, Content-Range",
    ));
}

fn respond_text(request: Request, status: StatusCode, text: &str) {
    let response = Response::from_string(text.to_string())
        .with_status_code(status)
        .with_header(response_header("Content-Type", "text/plain; charset=utf-8"))
        .with_header(response_header("Cache-Control", "no-store"))
        .with_header(response_header("Access-Control-Allow-Origin", "*"))
        .with_header(response_header(
            "Access-Control-Allow-Methods",
            "GET, HEAD, OPTIONS",
        ))
        .with_header(response_header("Access-Control-Allow-Headers", "Range"));
    let _ = request.respond(response);
}

fn respond_options(request: Request) {
    let response = Response::empty(StatusCode(204))
        .with_header(response_header("Access-Control-Allow-Origin", "*"))
        .with_header(response_header(
            "Access-Control-Allow-Methods",
            "GET, HEAD, OPTIONS",
        ))
        .with_header(response_header("Access-Control-Allow-Headers", "Range"))
        .with_header(response_header("Access-Control-Max-Age", "600"))
        .with_header(response_header("Cache-Control", "no-store"));
    let _ = request.respond(response);
}

pub fn run() {
    tauri::Builder::default()
        .manage(NativeMediaState::default())
        .invoke_handler(tauri::generate_handler![
            desktop_health,
            desktop_choose_local_directory,
            desktop_native_media_url,
            desktop_native_subtitle_file,
            desktop_baidu_hls_url
        ])
        .run(tauri::generate_context!())
        .expect("error while running LearningPyramid desktop client");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relative_path_normalization_can_allow_current_dir_for_native_project_root() {
        assert_eq!(
            normalize_relative_path(".", "learningObjectRoot", true)
                .expect("current dir should be accepted"),
            PathBuf::new()
        );
        assert!(normalize_relative_path(".", "materialId", false).is_err());
    }

    #[test]
    fn native_local_media_helpers_normalize_importable_paths() {
        assert_eq!(
            path_to_posix_string(&Path::new("chapter").join("lesson.mp4"))
                .expect("path should normalize"),
            "chapter/lesson.mp4"
        );
        assert!(is_importable_media_path(Path::new("lesson.mp4")));
        assert!(is_importable_media_path(Path::new("lesson.webm")));
        assert!(!is_importable_media_path(Path::new("notes.txt")));
    }

    #[test]
    fn baidu_hls_upstream_allowlist_accepts_baidu_playlist_and_pcs_cdn_hosts() {
        assert!(is_allowed_baidu_upstream_url(
            "https://pan.baidu.com/rest/2.0/xpan/file?method=streaming"
        ));
        assert!(is_allowed_baidu_upstream_url(
            "https://yqall06.baidupcs.com/file/segment.ts?access_token=redacted"
        ));
    }

    #[test]
    fn baidu_hls_upstream_allowlist_rejects_non_https_and_unrelated_hosts() {
        assert!(!is_allowed_baidu_upstream_url(
            "http://yqall06.baidupcs.com/file/segment.ts"
        ));
        assert!(!is_allowed_baidu_upstream_url(
            "https://example.com/file/segment.ts"
        ));
        assert!(!is_allowed_baidu_upstream_url(
            "https://notbaidupcs.com/file/segment.ts"
        ));
    }

    #[test]
    fn baidu_hls_playlist_normalization_accepts_pcs_cdn_segment_hosts() {
        let playlist = "#EXTM3U\n#EXTINF:4.000,\nhttps://yqall06.baidupcs.com/file/segment.ts?access_token=redacted\n";

        let normalized =
            normalize_baidu_hls_playlist(playlist, "https://pan.baidu.com/rest/2.0/xpan/file")
                .expect("pcs cdn segment host should be accepted");

        assert_eq!(normalized, playlist.trim());
    }
}
