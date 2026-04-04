CREATE TABLE IF NOT EXISTS global_settings_index (
    settings_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_cloud_accounts (
    account_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    avatar_url TEXT,
    access_token_ciphertext TEXT NOT NULL,
    refresh_token_ciphertext TEXT NOT NULL,
    expires_at TEXT,
    scope TEXT NOT NULL DEFAULT '',
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    disabled_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, provider, provider_user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_cloud_accounts_user_provider
ON user_cloud_accounts (user_id, provider, updated_at DESC);

CREATE TABLE IF NOT EXISTS instance_media_binding_index (
    project_id TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    playback_kind TEXT NOT NULL DEFAULT 'FILE',
    account_id TEXT,
    remote_file_id TEXT,
    remote_path TEXT,
    mime_type TEXT,
    size_bytes BIGINT,
    duration_ms BIGINT,
    source_payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at_ms BIGINT NOT NULL,
    PRIMARY KEY(project_id, instance_id),
    FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE,
    FOREIGN KEY(project_id, instance_id) REFERENCES instance_index(project_id, instance_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_instance_media_binding_index_project
ON instance_media_binding_index (project_id, source_kind, updated_at_ms DESC);
