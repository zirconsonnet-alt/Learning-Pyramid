from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.models.hls_cache_entry import HlsCacheEntry
from backend.system.auth_store import AuthStore
from backend.system.desktop_media_hls import current_hls_profile, prune_hls_cache


def _seed_hls_entry(
    auth_store: AuthStore,
    cache_root: Path,
    *,
    agent_id: str,
    cache_key: str,
    segment_name: str,
    content: bytes,
    created_at: str,
    last_accessed_at: str,
    expires_at: str,
) -> Path:
    file_path = cache_root / cache_key / segment_name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)
    auth_store.upsert_hls_cache_entry(
        HlsCacheEntry(
            cache_key=cache_key,
            project_id="proj_123",
            instance_id="inst_123",
            agent_id=agent_id,
            profile='{"heightMax":720}',
            segment_name=segment_name,
            file_path=str(file_path),
            size_bytes=len(content),
            created_at=created_at,
            last_accessed_at=last_accessed_at,
            expires_at=expires_at,
        )
    )
    return file_path


def _create_agent(auth_store: AuthStore) -> str:
    user = auth_store.create_user("owner@example.com", "password123")
    pairing = auth_store.create_desktop_agent_pairing_code(user.user_id)
    agent, _, _ = auth_store.pair_desktop_agent(
        pairing.pairing_code,
        device_name="BYLOU-PC",
        platform="windows",
        app_version="0.1.0",
    )
    return agent.agent_id


def test_current_hls_profile_uses_safer_defaults(monkeypatch) -> None:
    monkeypatch.delenv("PLM_AGENT_HLS_HEIGHT_MAX", raising=False)
    monkeypatch.delenv("PLM_AGENT_HLS_VIDEO_BITRATE", raising=False)
    monkeypatch.delenv("PLM_AGENT_HLS_AUDIO_BITRATE", raising=False)
    monkeypatch.delenv("PLM_AGENT_HLS_SEGMENT_SECONDS", raising=False)

    assert current_hls_profile() == {
        "heightMax": 720,
        "videoBitrate": "1200k",
        "audioBitrate": "96k",
        "segmentSeconds": 3,
    }


def test_prune_hls_cache_removes_expired_entries(monkeypatch, tmp_path: Path) -> None:
    cache_root = tmp_path / "desktop-cache"
    monkeypatch.setenv("PLM_AGENT_CACHE_DIR", str(cache_root))
    auth_store = AuthStore(db_path=tmp_path / "auth.sqlite3")
    agent_id = _create_agent(auth_store)

    expired_file = _seed_hls_entry(
        auth_store,
        cache_root,
        agent_id=agent_id,
        cache_key="cache-expired",
        segment_name="master.m3u8",
        content=b"#EXTM3U\n",
        created_at="2026-03-11T09:00:00+00:00",
        last_accessed_at="2026-03-11T09:05:00+00:00",
        expires_at="2026-03-11T09:10:00+00:00",
    )
    fresh_file = _seed_hls_entry(
        auth_store,
        cache_root,
        agent_id=agent_id,
        cache_key="cache-fresh",
        segment_name="master.m3u8",
        content=b"#EXTM3U\n#EXT-X-VERSION:3\n",
        created_at="2026-03-11T10:00:00+00:00",
        last_accessed_at="2026-03-11T10:05:00+00:00",
        expires_at="2026-03-12T10:05:00+00:00",
    )

    removed = prune_hls_cache(
        auth_store,
        now=datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert {(item.cache_key, item.segment_name) for item in removed} == {("cache-expired", "master.m3u8")}
    assert auth_store.get_hls_cache_entry("cache-expired", "master.m3u8") is None
    assert not expired_file.exists()
    assert auth_store.get_hls_cache_entry("cache-fresh", "master.m3u8") is not None
    assert fresh_file.exists()


def test_prune_hls_cache_evicts_least_recently_used_entries_when_over_limit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "desktop-cache"
    monkeypatch.setenv("PLM_AGENT_CACHE_DIR", str(cache_root))
    monkeypatch.setenv("PLM_AGENT_CACHE_MAX_BYTES", "10")
    auth_store = AuthStore(db_path=tmp_path / "auth.sqlite3")
    agent_id = _create_agent(auth_store)

    old_file = _seed_hls_entry(
        auth_store,
        cache_root,
        agent_id=agent_id,
        cache_key="cache-old",
        segment_name="segment000.ts",
        content=b"12345678",
        created_at="2026-03-11T08:00:00+00:00",
        last_accessed_at="2026-03-11T08:05:00+00:00",
        expires_at="2026-03-12T08:05:00+00:00",
    )
    fresh_file = _seed_hls_entry(
        auth_store,
        cache_root,
        agent_id=agent_id,
        cache_key="cache-fresh",
        segment_name="segment000.ts",
        content=b"abcdef",
        created_at="2026-03-11T09:00:00+00:00",
        last_accessed_at="2026-03-11T09:05:00+00:00",
        expires_at="2026-03-12T09:05:00+00:00",
    )

    removed = prune_hls_cache(
        auth_store,
        now=datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert {(item.cache_key, item.segment_name) for item in removed} == {("cache-old", "segment000.ts")}
    assert auth_store.get_hls_cache_entry("cache-old", "segment000.ts") is None
    assert not old_file.exists()
    assert auth_store.get_hls_cache_entry("cache-fresh", "segment000.ts") is not None
    assert fresh_file.exists()
