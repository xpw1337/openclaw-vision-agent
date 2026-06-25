"""Tests for sampler manifest generation and API-cost guardrails."""

import json

import pytest

from scripts.generate_sampler_manifests import load_cameras, render_manifest


def test_load_cameras_validates_and_renders_replicas_zero(tmp_path):
    registry = tmp_path / "cameras.json"
    registry.write_text(
        json.dumps(
            {
                "cameras": [
                    {
                        "camera_id": "cam-dock-1",
                        "zone": "dock",
                        "clip_file": "cam-dock-1.avi",
                        "display_name": "Dock 1",
                    },
                    {
                        "camera_id": "cam-lobby-1",
                        "zone": "lobby",
                        "clip_file": "cam-lobby-1.avi",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = render_manifest(load_cameras(registry))

    assert manifest.count("kind: Deployment") == 2
    assert manifest.count("\n  replicas: 0") == 2
    assert "value: \"cam-dock-1\"" in manifest
    assert "value: \"/app/data/clips/cam-lobby-1.avi\"" in manifest


def test_render_manifest_rejects_nonzero_sampler_replicas(tmp_path):
    registry = tmp_path / "cameras.json"
    registry.write_text(
        json.dumps({"cameras": [{"camera_id": "cam-1", "zone": "dock", "clip_file": "cam-1.avi"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="replicas=0"):
        render_manifest(load_cameras(registry), replicas=1)


def test_load_cameras_rejects_duplicate_ids(tmp_path):
    registry = tmp_path / "cameras.json"
    registry.write_text(
        json.dumps(
            {
                "cameras": [
                    {"camera_id": "cam-1", "zone": "dock", "clip_file": "cam-1.avi"},
                    {"camera_id": "cam-1", "zone": "dock", "clip_file": "cam-1b.avi"},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate camera_id"):
        load_cameras(registry)
