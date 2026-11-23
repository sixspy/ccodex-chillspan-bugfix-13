"""温谱导出（甲路径：格式切换与校验和重算同事务绑定，空摘要零增拒发）。"""
from __future__ import annotations

import csv
import hashlib
import io
import json

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import (
    FORMAL_EXPORT_PREDICATE,
    connect,
    now_iso,
    write_audit,
)
from locks import release, try_acquire
from models import SpectrumIn

router = APIRouter(tags=["spectrum"])


def _render_payload(batch, points: list, export_format: str) -> str:
    """按选定格式渲染正式导出载荷；校验和即对该载荷取摘要。"""
    if export_format == "json":
        return json.dumps(
            {
                "batch_code": batch["batch_code"],
                "generation": batch["generation"],
                "format": "json",
                "points": points,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["batch_code", "generation", "t", "c"])
    for p in points:
        writer.writerow(
            [
                batch["batch_code"],
                batch["generation"],
                p.get("t", ""),
                p.get("c", p.get("temp", "")),
            ]
        )
    return buf.getvalue()


def _checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _serialize(row) -> dict:
    d = dict(row)
    d["formally_issued"] = bool(d.get("formally_issued", 1))
    return d


def formal_exports_of_batch(conn, batch_id: int) -> list[dict]:
    """五处视图同源口径：只认校验和非空、已重算的正式导出。"""
    rows = conn.execute(
        f"""SELECT * FROM spectrum_exports
            WHERE batch_id=? AND {FORMAL_EXPORT_PREDICATE}
            ORDER BY id DESC""",
        (batch_id,),
    ).fetchall()
    return [_serialize(r) for r in rows]


@router.get("/api/spectrum")
def list_exports(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT s.*, b.batch_code FROM spectrum_exports s
               JOIN temp_batches b ON b.id=s.batch_id ORDER BY s.id DESC"""
        ).fetchall()
        return {"items": [_serialize(r) for r in rows]}


@router.post("/api/spectrum/export")
def export_spectrum(body: SpectrumIn, authorization: AuthHeader = None):
    user = require_writer(authorization)

    # 偏离写入格式摘要纪应当日封口：非法格式只记偏航审计，拒写业务，且不占批次锁
    try:
        export_format = body.normalized_format()
    except ValueError:
        with connect() as conn:
            write_audit(
                conn,
                user,
                "format_summary_yaw",
                f"batch:{body.batch_id}",
                {"rejected_format": body.export_format, "reason": "格式不在封口白名单"},
            )
            conn.commit()
        raise HTTPException(422, "导出格式偏离封口纪要，拒写")

    lock_key = f"batch:{body.batch_id}"
    with connect() as conn:
        # 双人同批换格式导出：须占批次锁，争用只记痕（先落痕提交再拒，避免回滚抹痕）
        if not try_acquire(conn, lock_key, user):
            conn.commit()
            raise HTTPException(409, "争用：后到只记争用，不写业务")
        try:
            batch = conn.execute(
                "SELECT * FROM temp_batches WHERE id=?", (body.batch_id,)
            ).fetchone()
            if not batch:
                raise HTTPException(404, "批次不存在")
            if batch["status"] != "已封批":
                raise HTTPException(409, "须先封批再导出温谱")
            points = json.loads(batch["temp_points"] or "[]")

            # 甲路径核心：格式渲染与校验和重算在同一事务内绑定写回
            payload = _render_payload(batch, points, export_format)
            checksum = _checksum(payload)

            # 空摘要硬闸：零增拒发，禁止空校验和正式导出对外下发
            if not checksum:
                write_audit(
                    conn,
                    user,
                    "format_summary_yaw",
                    f"batch:{body.batch_id}",
                    {"reason": "校验和重算为空，拒发", "export_format": export_format},
                )
                conn.commit()
                raise HTTPException(409, "校验和为空，正式导出行零增拒发")

            ref = f"SP-{batch['batch_code']}-G{batch['generation']}-{export_format.upper()}"
            dup = conn.execute(
                "SELECT id FROM spectrum_exports WHERE export_ref=?", (ref,)
            ).fetchone()
            if dup:
                raise HTTPException(409, "该代该格式温谱已导出")
            now = now_iso()
            cur = conn.execute(
                """INSERT INTO spectrum_exports(batch_id,export_ref,point_count,checksum,
                   export_format,checksum_state,formally_issued,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    body.batch_id,
                    ref,
                    len(points),
                    checksum,
                    export_format,
                    "已重算",
                    1,
                    "已导出",
                    now,
                ),
            )
            write_audit(
                conn,
                user,
                "spectrum_export",
                ref,
                {
                    "checksum": checksum,
                    "export_format": export_format,
                    "checksum_state": "已重算",
                },
            )
            conn.commit()
            return {
                "id": cur.lastrowid,
                "export_ref": ref,
                "point_count": len(points),
                "checksum": checksum,
                "export_format": export_format,
                "checksum_state": "已重算",
                "formally_issued": True,
                "status": "已导出",
            }
        finally:
            release(conn, lock_key, user)


@router.get("/api/spectrum/{export_ref}")
def get_export(export_ref: str, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        row = conn.execute(
            """SELECT s.*, b.temp_points, b.batch_code FROM spectrum_exports s
               JOIN temp_batches b ON b.id=s.batch_id WHERE s.export_ref=?""",
            (export_ref,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "导出不存在")
        data = _serialize(row)
        data["temp_points"] = json.loads(data["temp_points"] or "[]")
        return data
