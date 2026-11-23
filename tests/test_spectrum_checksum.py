"""BUGFIX-13 红测：格式切换与校验和重算必须同事务，空摘要不得对外下发。

口径（甲路径，禁止与乙路径影子稿混用）：
- 格式变更 => 校验和须在同一事务重算写回；
- 校验和为空 => 正式导出行零增、拒绝下发；
- 不允许任何影子/草稿态导出对外可见；
- 双人同批换格式导出须占批次锁，争用只记痕；
- 偏离写入格式摘要纪应当日封口并拒写。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app
from db import connect, init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _auth(c: TestClient, user: str = "admin") -> dict:
    tok = c.post(
        "/api/login", json={"username": user, "password": "123456"}
    ).json()["token"]
    return {"Authorization": "Bearer " + tok}


def _sealed_batch(c: TestClient, h: dict, code: str = "TB-RED-001") -> int:
    chambers = c.get("/api/chambers", headers=h).json()["items"]
    ch = next(x for x in chambers if x["chamber_code"] == "CK-HN-03")
    probes = c.get(f"/api/probes?chamber_id={ch['id']}", headers=h).json()["items"]
    probe = next(p for p in probes if p["probe_code"] == "PR-HN-C1")
    points = [
        {"t": "08:00", "c": 2.1},
        {"t": "09:00", "c": 3.4},
        {"t": "10:00", "c": 2.8},
    ]
    batch = c.post(
        "/api/batches",
        headers=h,
        json={
            "chamber_id": ch["id"],
            "probe_id": probe["id"],
            "cargo_ref": "红测货载-空摘要禁发",
            "temp_points": points,
            "batch_code": code,
        },
    ).json()
    seal = c.post("/api/seals", headers=h, json={"batch_id": batch["id"]})
    assert seal.status_code == 200
    return batch["id"]


def test_red_a_format_switch_must_recompute_checksum_or_reject_empty():
    """失败测甲：盯空摘要仍导出。

    修复后两种合法结局二选一：
    1. 带格式导出成功且 checksum 非空，并与同载荷同格式重算值一致；
    2. 无法同事务重算时正式导出行零增（拒发）。
    绝不容忍 checksum == "" 的正式导出。
    """
    c = TestClient(app)
    h = _auth(c)
    batch_id = _sealed_batch(c, h)
    with connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) c FROM spectrum_exports WHERE batch_id=?",
            (batch_id,),
        ).fetchone()["c"]

    r = c.post(
        "/api/spectrum/export",
        headers=h,
        json={"batch_id": batch_id, "export_format": "csv"},
    )
    assert r.status_code == 200, r.text
    data = r.json()

    # 甲路径硬口径：空摘要不得下发
    assert data["checksum"], "空校验和不得作为正式导出下发"
    assert data["export_format"] == "csv"
    assert len(data["checksum"]) == 16

    # 落库行与接口回读同源、非空
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM spectrum_exports WHERE export_ref=?",
            (data["export_ref"],),
        ).fetchone()
        assert row is not None
        assert row["checksum"] == data["checksum"]
        assert row["checksum"] != ""
        after = conn.execute(
            "SELECT COUNT(*) c FROM spectrum_exports WHERE batch_id=?",
            (batch_id,),
        ).fetchone()["c"]
        assert after == before + 1

    got = c.get(f"/api/spectrum/{data['export_ref']}", headers=h).json()
    assert got["checksum"] == data["checksum"]
    assert got["checksum"]


def test_red_b_no_shadow_draft_visible_before_promotion():
    """失败测乙：盯影子稿未晋升却已对外。

    甲路径不引入影子稿：任何对外读面（列表、详情、互证、仪表盘）
    都不得出现影子/草稿/待晋升态导出；空摘要遗痕不得被当作正式
    已导出发放，只可作为待重算/作废遗痕单独呈现。
    """
    c = TestClient(app)
    h = _auth(c)

    # 夹具遗痕：格式已换、校验和为空，状态却写着“已导出”
    legacy = c.get("/api/spectrum", headers=h).json()["items"]
    bad = [x for x in legacy if x["export_ref"] == "SP-TB-CK-HD-01-002-G2"]
    assert bad, "复现夹具必须经文件库装载"
    row = bad[0]
    assert row["checksum"] == ""

    # 对外读面不得把空摘要遗痕当正式导出
    assert row["status"] != "已导出" or row.get("checksum_state") == "待重算"
    assert row.get("formally_issued") is False

    # 任何影子/草稿态都不得对外
    shadow_states = {"影子稿", "草稿", "待晋升", "待哈希"}
    for x in legacy:
        assert x["status"] not in shadow_states
        if x.get("checksum") in (None, ""):
            assert x.get("formally_issued") is False

    # 互证视图：空摘要不得计入正式温谱导出
    proof = c.get("/api/proof/batch/TB-CK-HD-01-002", headers=h).json()
    assert proof["spectrum_exports"] == 0
    assert proof["spectrum_matches_seal"] is False

    # 仪表盘同样不得把遗痕计入正式导出
    dash = c.get("/api/dashboard", headers=h).json()
    assert dash["spectrum_exports"] == 0

    # 全表不得存在任何影子/草稿态导出行
    with connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) c FROM spectrum_exports WHERE status IN (?,?,?,?)",
            ("影子稿", "草稿", "待晋升", "待哈希"),
        ).fetchone()["c"]
        assert n == 0


def test_red_c_concurrent_format_switch_holds_batch_lock_contention_only():
    """争用失败测：二人同批并发换格式，后到只记争用不写业务。"""
    c = TestClient(app)
    h1 = _auth(c, "admin")
    h2 = _auth(c, "ops")
    batch_id = _sealed_batch(c, h1, code="TB-RED-LOCK-001")

    # 第一人先占批次锁
    lock_key = f"batch:{batch_id}"
    acq = c.post(
        "/api/locks/acquire", headers=h1, json={"lock_key": lock_key}
    )
    assert acq.status_code == 200

    # 第二人换格式导出：须 409，且不产生任何导出/遗痕
    with connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) c FROM spectrum_exports WHERE batch_id=?",
            (batch_id,),
        ).fetchone()["c"]
    r = c.post(
        "/api/spectrum/export",
        headers=h2,
        json={"batch_id": batch_id, "export_format": "csv"},
    )
    assert r.status_code == 409, r.text
    with connect() as conn:
        after = conn.execute(
            "SELECT COUNT(*) c FROM spectrum_exports WHERE batch_id=?",
            (batch_id,),
        ).fetchone()["c"]
        assert after == before
        cont = conn.execute(
            "SELECT * FROM contention_log WHERE lock_key=? ORDER BY id DESC",
            (lock_key,),
        ).fetchall()
        assert any(d["actor"] == "ops" for d in cont), "争用必须只记痕"

    # 第一人放行后，正式导出仍须带非空校验和
    c.post("/api/locks/release", headers=h1, json={"lock_key": lock_key})
    ok = c.post(
        "/api/spectrum/export",
        headers=h1,
        json={"batch_id": batch_id, "export_format": "json"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["checksum"]


def test_red_d_format_summary_deviation_is_rejected_and_audited():
    """偏离写入格式摘要纪应当日封口：非法格式拒写并留审计偏航痕。"""
    c = TestClient(app)
    h = _auth(c)
    batch_id = _sealed_batch(c, h, code="TB-RED-YAW-001")
    with connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) c FROM spectrum_exports WHERE batch_id=?",
            (batch_id,),
        ).fetchone()["c"]

    r = c.post(
        "/api/spectrum/export",
        headers=h,
        json={"batch_id": batch_id, "export_format": "yaml"},
    )
    assert r.status_code in (409, 422), r.text
    with connect() as conn:
        after = conn.execute(
            "SELECT COUNT(*) c FROM spectrum_exports WHERE batch_id=?",
            (batch_id,),
        ).fetchone()["c"]
        assert after == before
        yaw = conn.execute(
            "SELECT * FROM audit_trail WHERE action='format_summary_yaw' ORDER BY id DESC"
        ).fetchall()
        assert yaw, "格式摘要偏航必须记审计"
