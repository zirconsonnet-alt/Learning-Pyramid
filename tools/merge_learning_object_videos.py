"""
One-off store maintenance: merge duplicated "videos" LearningObject trees into one.

This repo historically allowed repeated material-tree imports that appended multiple identical
LearningObject forests (roots titled "videos"). This script:
  - Keeps a single root container (default title: "videos")
  - Removes the synthetic second-layer "Files" containers
  - Merges same-titled leaves across roots (e.g. "1.mp4") by keeping a single canonical Instance
  - Remaps RecallPoint.anchor.instanceId and LearningObjectLeaf.instanceId accordingly
  - Deletes now-unreferenced duplicate Instances and LearningObjectNodes

Usage (PowerShell):
  python tools/merge_learning_object_videos.py --store .plm_store.json --project proj_000014
  python tools/merge_learning_object_videos.py --store .plm_store.json --project proj_000014 --dry-run
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


_INT_SUFFIX_RE = re.compile(r"(\d+)$")


def _num_suffix(s: str) -> int:
    m = _INT_SUFFIX_RE.search(str(s))
    return int(m.group(1)) if m else 10**18


def _min_by_num_then_text(ids: Iterable[str]) -> str:
    xs = list(ids)
    if not xs:
        raise ValueError("expected non-empty ids")
    return min(xs, key=lambda x: (_num_suffix(x), str(x)))


def _sorted_unique(xs: Iterable[str]) -> list[str]:
    out = sorted(set(xs), key=lambda x: (str(x)))
    return out


def _backup_path(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return p.with_name(f"{p.name}.bak-{ts}")


def _walk_strings(obj: Any) -> Iterable[str]:
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
        return
    if isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)
        return
    if isinstance(obj, str):
        yield obj


@dataclass(frozen=True)
class _LeafRef:
    leaf_node_id: str
    leaf_title: str
    instance_id: str
    material_id: str


def _validate_files_layer_pattern(nodes: dict[str, dict[str, Any]], root_id: str) -> tuple[str, list[str]]:
    root = nodes[root_id]
    if root.get("kind") != "CONTAINER":
        raise ValueError(f"root {root_id} is not CONTAINER")
    if root.get("parentId") is not None:
        raise ValueError(f"root {root_id} parentId must be null")
    children = list(root.get("children") or [])
    if len(children) != 1:
        raise ValueError(f"root {root_id} expected exactly 1 child (Files), got {len(children)}")
    files_id = str(children[0])
    if files_id not in nodes:
        raise ValueError(f"root {root_id} child not resolvable: {files_id}")
    files = nodes[files_id]
    if files.get("kind") != "CONTAINER" or files.get("title") != "Files":
        raise ValueError(f"root {root_id} child is not Files container: {files_id}")
    if files.get("parentId") != root_id:
        raise ValueError(f"Files container {files_id} parentId mismatch (want {root_id})")

    leaf_ids: list[str] = []
    for cid in list(files.get("children") or []):
        leaf_id = str(cid)
        if leaf_id not in nodes:
            raise ValueError(f"leaf not resolvable: {leaf_id}")
        leaf = nodes[leaf_id]
        if leaf.get("kind") != "LEAF":
            raise ValueError(f"Files child is not LEAF: {leaf_id}")
        if leaf.get("parentId") != files_id:
            raise ValueError(f"leaf {leaf_id} parentId mismatch (want {files_id})")
        leaf_ids.append(leaf_id)
    return files_id, leaf_ids


def _validate_tree(nodes: dict[str, dict[str, Any]]) -> None:
    # Structural checks similar to commit-time validator.
    def kind(nid: str) -> str:
        return str(nodes[nid].get("kind") or "")

    roots = [nid for nid, n in nodes.items() if n.get("parentId") is None]
    if len(roots) != 1:
        raise ValueError(f"expected exactly 1 root, got {len(roots)}: {roots[:10]}")

    # children uniqueness + bidirectional consistency + homogeneity
    for nid, n in nodes.items():
        if kind(nid) != "CONTAINER":
            continue
        ch = [str(x) for x in list(n.get("children") or [])]
        if len(ch) != len(set(ch)):
            raise ValueError(f"Duplicate child in container {nid}")
        child_kinds = set()
        for cid in ch:
            if cid not in nodes:
                raise ValueError(f"Dangling child id {cid} in container {nid}")
            if nodes[cid].get("parentId") != nid:
                raise ValueError(f"Bidirectional inconsistency: child.parentId {cid} != {nid}")
            child_kinds.add(kind(cid))
        if len(child_kinds) > 1:
            raise ValueError(f"Homogeneous children violated in container {nid}: {child_kinds}")

    for nid, n in nodes.items():
        pid = n.get("parentId")
        if pid is None:
            continue
        pid = str(pid)
        if pid not in nodes:
            raise ValueError(f"parent not resolvable: {nid} -> {pid}")
        if kind(pid) != "CONTAINER":
            raise ValueError(f"parent must be container: {nid} -> {pid}")
        pch = [str(x) for x in list(nodes[pid].get("children") or [])]
        if nid not in set(pch):
            raise ValueError(f"Bidirectional inconsistency: parent.children missing {nid} under {pid}")

    # Cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {nid: WHITE for nid in nodes.keys()}

    def dfs(u: str) -> None:
        color[u] = GRAY
        nu = nodes[u]
        if kind(u) == "CONTAINER":
            for cid in list(nu.get("children") or []):
                v = str(cid)
                if v not in nodes:
                    raise ValueError(f"Dangling child id {v}")
                if color[v] == GRAY:
                    raise ValueError("Cycle detected")
                if color[v] == WHITE:
                    dfs(v)
        color[u] = BLACK

    for nid in list(nodes.keys()):
        if color[nid] == WHITE:
            dfs(nid)


def _validate_instance_bindings(
    *,
    instances: dict[str, dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    recall_points: dict[str, dict[str, Any]],
) -> None:
    # All leaf instance ids must exist, and must be unique across leaves.
    leaf_iids: list[str] = []
    for nid, n in nodes.items():
        if n.get("kind") != "LEAF":
            continue
        iid = str(n.get("instanceId") or "")
        if not iid:
            raise ValueError(f"LEAF missing instanceId: {nid}")
        if iid not in instances:
            raise ValueError(f"LEAF instanceId not resolvable: {nid} -> {iid}")
        leaf_iids.append(iid)
    if len(leaf_iids) != len(set(leaf_iids)):
        raise ValueError("InstanceId already bound by another LearningObjectLeaf (duplicate leaf bindings)")

    # All recall point anchors must be resolvable.
    for rpid, rp in recall_points.items():
        anchor = rp.get("anchor") or {}
        iid = str(anchor.get("instanceId") or "")
        if not iid:
            raise ValueError(f"RecallPoint missing anchor.instanceId: {rpid}")
        if iid not in instances:
            raise ValueError(f"RecallPoint anchor.instanceId not resolvable: {rpid} -> {iid}")


def merge_project(
    project: dict[str, Any],
    *,
    root_title: str,
    dry_run: bool,
) -> dict[str, Any]:
    nodes_in: dict[str, dict[str, Any]] = project.get("learningObjectNodes") or {}
    nodes: dict[str, dict[str, Any]] = nodes_in
    if not nodes:
        return {"changed": False, "reason": "no learningObjectNodes"}

    instances_in: dict[str, dict[str, Any]] = project.get("instances") or {}
    recall_points_in: dict[str, dict[str, Any]] = project.get("recallPoints") or {}

    # Work on copies so --dry-run never mutates in-memory input.
    instances: dict[str, dict[str, Any]] = copy.deepcopy(instances_in)
    recall_points: dict[str, dict[str, Any]] = copy.deepcopy(recall_points_in)

    # Identify roots.
    root_ids = [nid for nid, n in nodes.items() if n.get("kind") == "CONTAINER" and n.get("parentId") is None]
    candidate_root_ids = [nid for nid in root_ids if str(nodes[nid].get("title") or "") == root_title]

    if len(candidate_root_ids) == 0:
        return {"changed": False, "reason": f"no roots titled {root_title!r}"}

    extra_roots = [nid for nid in root_ids if nid not in set(candidate_root_ids)]
    if extra_roots:
        raise ValueError(f"Refusing to merge: found other roots besides {root_title!r}: {extra_roots}")

    # Validate shape and collect leaves.
    all_leaf_refs: list[_LeafRef] = []
    files_container_ids: list[str] = []
    for rid in candidate_root_ids:
        files_id, leaf_ids = _validate_files_layer_pattern(nodes, rid)
        files_container_ids.append(files_id)
        for leaf_id in leaf_ids:
            leaf = nodes[leaf_id]
            title = str(leaf.get("title") or "")
            iid = str(leaf.get("instanceId") or "")
            if not title or not iid:
                raise ValueError(f"leaf missing title/instanceId: {leaf_id}")
            inst = instances.get(iid)
            if inst is None:
                raise ValueError(f"leaf instanceId not resolvable: {leaf_id} -> {iid}")
            mid = str(inst.get("materialId") or "")
            if not mid:
                raise ValueError(f"Instance missing materialId: {iid}")
            all_leaf_refs.append(_LeafRef(leaf_node_id=leaf_id, leaf_title=title, instance_id=iid, material_id=mid))

    # Group by leaf title (same-name merge).
    by_title: dict[str, list[_LeafRef]] = defaultdict(list)
    for ref in all_leaf_refs:
        by_title[ref.leaf_title].append(ref)

    # Sanity: title -> materialId must be single-valued (avoid accidental cross-dir merge).
    for title, refs in by_title.items():
        mats = {r.material_id for r in refs}
        if len(mats) != 1:
            raise ValueError(f"Cannot merge title {title!r}: multiple materialIds detected: {sorted(mats)}")

    # Canonical selection.
    canonical_instance_by_title: dict[str, str] = {}
    canonical_leaf_by_title: dict[str, str] = {}
    instance_remap: dict[str, str] = {}
    duplicate_instance_ids: set[str] = set()
    for title, refs in by_title.items():
        inst_ids = [r.instance_id for r in refs]
        leaf_ids = [r.leaf_node_id for r in refs]
        canonical_iid = _min_by_num_then_text(inst_ids)
        canonical_lid = _min_by_num_then_text(leaf_ids)
        canonical_instance_by_title[title] = canonical_iid
        canonical_leaf_by_title[title] = canonical_lid
        for iid in inst_ids:
            instance_remap[iid] = canonical_iid
            if iid != canonical_iid:
                duplicate_instance_ids.add(iid)

    keep_root_id = _min_by_num_then_text(candidate_root_ids)

    # Apply remaps (in-place).
    changed_rp = 0
    for rp in recall_points.values():
        anchor = rp.get("anchor")
        if not isinstance(anchor, dict):
            continue
        old_iid = str(anchor.get("instanceId") or "")
        new_iid = instance_remap.get(old_iid)
        if new_iid and new_iid != old_iid:
            anchor["instanceId"] = new_iid
            changed_rp += 1

    # Rebuild LearningObjectNodes (single root + leaves).
    keep_leaf_ids = set(canonical_leaf_by_title.values())
    new_nodes: dict[str, dict[str, Any]] = {}

    root_out = copy.deepcopy(nodes[keep_root_id])
    root_out["parentId"] = None

    # Sort children by title for determinism.
    leaf_ids_sorted = sorted(
        keep_leaf_ids,
        key=lambda lid: (str(nodes[lid].get("title") or ""), _num_suffix(lid), lid),
    )
    root_out["children"] = leaf_ids_sorted
    new_nodes[keep_root_id] = root_out

    updated_leaf_instance = 0
    for lid in leaf_ids_sorted:
        leaf_in = nodes[lid]
        title = str(leaf_in.get("title") or "")
        if not title:
            raise ValueError(f"canonical leaf missing title: {lid}")
        canonical_iid = canonical_instance_by_title[title]
        leaf_out = copy.deepcopy(leaf_in)
        leaf_out["parentId"] = keep_root_id
        if leaf_out.get("instanceId") != canonical_iid:
            leaf_out["instanceId"] = canonical_iid
            updated_leaf_instance += 1
        new_nodes[lid] = leaf_out

    # Update Instances: delete duplicates if safe.
    used_instance_ids = {str(n.get("instanceId")) for n in new_nodes.values() if n.get("kind") == "LEAF"}
    anchored_instance_ids = {
        str((rp.get("anchor") or {}).get("instanceId")) for rp in recall_points.values() if isinstance(rp, dict)
    }
    if any(iid not in instances for iid in used_instance_ids | anchored_instance_ids):
        missing = sorted([iid for iid in (used_instance_ids | anchored_instance_ids) if iid not in instances])
        raise ValueError(f"After remap, some instanceIds are missing from instances dict: {missing[:10]}")

    # Ensure duplicates are not referenced any more (except in instances dict itself).
    # We check direct references via leaves + recall points; if other structures reference instances,
    # we refuse to delete to avoid breaking hidden links.
    duplicates_to_delete: set[str] = set()
    for iid in duplicate_instance_ids:
        if iid in used_instance_ids:
            continue
        if iid in anchored_instance_ids:
            continue
        duplicates_to_delete.add(iid)

    # Conservative: scan for any remaining string occurrences in the whole project object.
    # This catches other domains (for example ASR artifacts) that might store instanceId strings.
    other_payload = {k: v for k, v in project.items() if k not in {"instances", "learningObjectNodes", "recallPoints"}}
    other_strings = set(_walk_strings(other_payload))
    unsafe = sorted([iid for iid in duplicates_to_delete if iid in other_strings])
    if unsafe:
        raise ValueError(
            "Refusing to delete duplicate instances still referenced elsewhere in project payload: "
            + ", ".join(unsafe[:10])
        )

    instances_deleted = 0
    for iid in duplicates_to_delete:
        if iid in instances:
            del instances[iid]
            instances_deleted += 1

    # Final validation (post-image).
    _validate_tree(new_nodes)
    _validate_instance_bindings(instances=instances, nodes=new_nodes, recall_points=recall_points)

    if not dry_run:
        project["learningObjectNodes"] = new_nodes
        project["instances"] = instances
        project["recallPoints"] = recall_points

    return {
        "changed": True,
        "keepRootId": keep_root_id,
        "rootsMerged": len(candidate_root_ids),
        "filesContainersRemoved": len(files_container_ids),
        "uniqueLeavesKept": len(keep_leaf_ids),
        "learningObjectNodesBefore": len(nodes),
        "learningObjectNodesAfter": len(new_nodes),
        "instancesBefore": len(instances_in),
        "instancesAfter": len(instances),
        "instancesDeleted": instances_deleted,
        "recallPointsRemapped": changed_rp,
        "leafInstanceIdsUpdated": updated_leaf_instance,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=".plm_store.json", help="path to store JSON (default: .plm_store.json)")
    ap.add_argument("--project", default="", help="project id to operate on (default: all projects)")
    ap.add_argument("--root-title", default="videos", help="root container title to merge (default: videos)")
    ap.add_argument("--dry-run", action="store_true", help="validate and print report, but do not write changes")
    args = ap.parse_args(argv)

    store_path = Path(args.store)
    if not store_path.exists():
        print(f"Store not found: {store_path}", file=sys.stderr)
        return 2

    data = json.loads(store_path.read_text(encoding="utf-8"))
    projects: dict[str, Any] = data.get("projects") or {}
    if not isinstance(projects, dict):
        print("Invalid store: projects must be an object", file=sys.stderr)
        return 2

    target_projects: list[str]
    if args.project:
        if args.project not in projects:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        target_projects = [args.project]
    else:
        target_projects = sorted(projects.keys())

    any_changed = False
    reports: dict[str, Any] = {}
    for pid in target_projects:
        rep = merge_project(projects[pid], root_title=args.root_title, dry_run=args.dry_run)
        reports[pid] = rep
        any_changed = any_changed or bool(rep.get("changed"))

    print(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))

    if args.dry_run or not any_changed:
        return 0

    # Backup + write.
    bak = _backup_path(store_path)
    bak.write_text(store_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Keep output style aligned with backend persistence (minified + stable keys).
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    store_path.write_text(text, encoding="utf-8")
    print(f"\nWrote: {store_path}")
    print(f"Backup: {bak}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
