"""Tests for enhance_cluster script."""

import json
from pathlib import Path

import pytest

import scripts.enhance_cluster as ec


VALID_CLUSTER_JSON = json.dumps(
    [
        {"cluster_label": "over-compression", "items": ["item 1", "item 2"]},
        {"cluster_label": "formatting", "items": ["item 3"]},
    ]
)

EMPTY_CLUSTER_JSON = json.dumps([])

INVALID_JSON_RESPONSE = "not valid json {"

NON_LIST_JSON = json.dumps({"not": "a list"})


def test_valid_json_clusters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.enhance_cluster.generate_with_timeout",
        lambda **kwargs: VALID_CLUSTER_JSON,
    )

    result = ec.cluster_backlog("some backlog text")
    assert len(result) == 2
    first_cluster = result[0]
    assert isinstance(first_cluster, dict)
    assert first_cluster.get("cluster_label") == "over-compression"
    cluster_items = first_cluster.get("items")
    assert isinstance(cluster_items, list)
    assert len(cluster_items) == 2


def test_empty_backlog() -> None:
    result = ec.cluster_backlog("")
    assert result == []


def test_whitespace_only_backlog() -> None:
    result = ec.cluster_backlog("   \n  \n  ")
    assert result == []


def test_invalid_json_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.enhance_cluster.generate_with_timeout",
        lambda **kwargs: INVALID_JSON_RESPONSE,
    )

    with pytest.raises(ec.ClusteringError, match="invalid JSON"):
        ec.cluster_backlog("backlog")


def test_non_list_json_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.enhance_cluster.generate_with_timeout",
        lambda **kwargs: NON_LIST_JSON,
    )

    with pytest.raises(ec.ClusteringError, match="not a list"):
        ec.cluster_backlog("backlog")


def test_empty_llm_response_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.enhance_cluster.generate_with_timeout",
        lambda **kwargs: "",
    )

    with pytest.raises(ec.ClusteringError, match="empty response"):
        ec.cluster_backlog("backlog")


def test_strips_json_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.enhance_cluster.generate_with_timeout",
        lambda **kwargs: "```json\n" + VALID_CLUSTER_JSON + "\n```",
    )

    result = ec.cluster_backlog("backlog")
    assert len(result) == 2


def test_main_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        "scripts.enhance_cluster.generate_with_timeout",
        lambda **kwargs: VALID_CLUSTER_JSON,
    )

    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("backlog text"))

    ret = ec.main(["--stdin"])
    assert ret == 0

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert len(result) == 2


def test_main_with_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        "scripts.enhance_cluster.generate_with_timeout",
        lambda **kwargs: VALID_CLUSTER_JSON,
    )

    backlog = tmp_path / "backlog.txt"
    backlog.write_text("some backlog", encoding="utf-8")

    ret = ec.main([str(backlog)])
    assert ret == 0

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert len(result) == 2
