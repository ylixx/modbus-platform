#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_and_commit_db.py — 测试期数据库瘦身 + 入库工具

用途：
  每次执行：
    1. 停止后端（uvicorn，端口 8000），释放对 SQLite 的占用，便于 VACUUM 独占。
    2. 把 WAL 合并回主库（wal_checkpoint TRUNCATE），保证主库文件是最新状态。
    3. 删除时序历史表中「N 天前」的数据：
         - tag_history    按 recorded_at
         - tag_aggregate 按 bucket_time
       （只有这两张表带时间戳、且是体积主要来源；其余 27 张表为设备/用户/权限/SCADA
         配置等小表，没有「按天清理」语义，误删会破坏配置，故不在此清理。）
    4. VACUUM 重建数据库，回收被删除行占用的空间，真正缩小文件。
    5. 再次 checkpoint，确保主库文件最新、WAL 为空。
    6. git add 主库 + commit + push 到远端（SSH）。
    7. 重新拉起后端，方便继续测试。

注意：
  - 需要被 git 跟踪的是主库文件 backend/modbus_platform.db（*.db-wal / *.db-shm 已被忽略）。
  - VACUUM 需要独占数据库，所以必须先停后端。
  - 推送走 SSH，需在允许联网的环境下运行（git push 可能需要 SSH key / agent）。

用法：
  python scripts/clean_and_commit_db.py [--days 1] [--no-restart] [--no-push] [--dry-run]
"""

import argparse
import os
import sqlite3
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "backend", "modbus_platform.db")
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
BACKEND_PORT = 8000
RETENTION_DAYS = 1


def log(msg):
    print(f"[clean_db] {msg}", flush=True)


def sh(cmd, cwd=None, check=True):
    """执行 shell 命令，返回 (rc, stdout, stderr)。"""
    r = subprocess.run(cmd, shell=True, cwd=cwd or REPO_ROOT,
                       capture_output=True, text=True, errors="ignore")
    if check and r.returncode != 0:
        log(f"命令失败 ({r.returncode}): {cmd}")
        if (r.stderr or "").strip():
            log(r.stderr.strip())
    return r.returncode, r.stdout or "", r.stderr or ""


def db_size_mb():
    return os.path.getsize(DB_PATH) / 1024.0 / 1024.0


def current_branch():
    rc, out, _ = sh("git rev-parse --abbrev-ref HEAD", check=False)
    return out.strip() if rc == 0 and out.strip() else "master"


def find_pid_on_port(port):
    """解析 netstat -ano，返回监听该端口的 PID（无则 None）。"""
    rc, out, _ = sh("netstat -ano", check=False)
    if rc != 0:
        return None
    for line in out.splitlines():
        if "LISTENING" not in line or f":{port}" not in line:
            continue
        parts = line.split()
        for i, p in enumerate(parts):
            if p.endswith(f":{port}):"):  # 形如 127.0.0.1:8000
                continue
            if p.endswith(f":{port}"):
                pid = parts[-1]
                if pid.isdigit():
                    return int(pid)
    return None


def stop_backend():
    pid = find_pid_on_port(BACKEND_PORT)
    if not pid:
        log("未检测到后端进程在端口 %d 监听，跳过停止。" % BACKEND_PORT)
        return
    log(f"停止后端进程 PID={pid} ...")
    rc, _, _ = sh(f"taskkill /PID {pid} /F", check=False)
    if rc != 0:
        log("taskkill 失败，请手动结束后端后再试。")
        sys.exit(1)
    # 等待端口释放
    for _ in range(20):
        if find_pid_on_port(BACKEND_PORT) is None:
            log("后端已停止。")
            return
        time.sleep(0.5)
    log("警告：端口 %d 仍未释放，VACUUM 可能失败。" % BACKEND_PORT)


def detect_venv_python():
    for name in (".venv", "venv"):
        p = os.path.join(BACKEND_DIR, name, "Scripts", "python.exe")
        if os.path.exists(p):
            return p
    raise FileNotFoundError("未找到后端 venv（.venv / venv 均不存在）")


def start_backend():
    venv_py = detect_venv_python()
    log_dir = os.path.join(BACKEND_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    logf = open(os.path.join(log_dir, "backend.log"), "a")
    DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)
    log(f"重新拉起后端: {venv_py} -m uvicorn app.main:app --port {BACKEND_PORT}")
    subprocess.Popen(
        [venv_py, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
        cwd=BACKEND_DIR, stdout=logf, stderr=subprocess.STDOUT,
        creationflags=DETACHED,
    )
    # 简单探测就绪
    for _ in range(30):
        if find_pid_on_port(BACKEND_PORT) is not None:
            log("后端已重新启动（端口 %d 监听中）。" % BACKEND_PORT)
            return
        time.sleep(1)
    log("警告：后端似乎未就绪，请检查 backend/logs/backend.log。")


def clean_and_vacuum(days, dry_run):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 1) 先把 WAL 合并回主库
    cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.commit()

    # 2) 删前计数
    h_before = cur.execute("SELECT COUNT(*) FROM tag_history").fetchone()[0]
    a_before = cur.execute("SELECT COUNT(*) FROM tag_aggregate").fetchone()[0]

    cutoff_h = f"-{days} day"
    cutoff_a = f"-{days} day"
    if dry_run:
        dh = cur.execute(
            "SELECT COUNT(*) FROM tag_history WHERE recorded_at < datetime('now', ?)",
            (cutoff_h,)).fetchone()[0]
        da = cur.execute(
            "SELECT COUNT(*) FROM tag_aggregate WHERE bucket_time < datetime('now', ?)",
            (cutoff_a,)).fetchone()[0]
        log(f"[dry-run] tag_history 将删除 {dh} 行（共 {h_before} 行，保留 {h_before - dh} 行）")
        log(f"[dry-run] tag_aggregate 将删除 {da} 行（共 {a_before} 行，保留 {a_before - da} 行）")
        conn.close()
        return h_before, a_before, 0, 0

    # 3) 删除 N 天前的数据
    cur.execute("DELETE FROM tag_history WHERE recorded_at < datetime('now', ?)", (cutoff_h,))
    cur.execute("DELETE FROM tag_aggregate WHERE bucket_time < datetime('now', ?)", (cutoff_a,))
    conn.commit()

    h_after = cur.execute("SELECT COUNT(*) FROM tag_history").fetchone()[0]
    a_after = cur.execute("SELECT COUNT(*) FROM tag_aggregate").fetchone()[0]
    log(f"tag_history: {h_before} -> {h_after}（删除 {h_before - h_after} 行）")
    log(f"tag_aggregate: {a_before} -> {a_after}（删除 {a_before - a_after} 行）")

    # 4) 再次合并 WAL，然后关闭连接，准备 VACUUM
    cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.commit()
    conn.close()

    # 5) VACUUM 需要独占，使用 autocommit 连接
    size_before = db_size_mb()
    conn2 = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        conn2.execute("VACUUM")
        log("VACUUM 完成。")
    except Exception as e:
        log(f"VACUUM 失败（可能仍有连接占用）：{e}")
    conn2.close()

    # 6) 最终 checkpoint，确保主库最新、WAL 为空
    conn3 = sqlite3.connect(DB_PATH)
    conn3.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn3.commit()
    conn3.close()

    size_after = db_size_mb()
    log(f"数据库文件: {size_before:.2f} MB -> {size_after:.2f} MB")
    return h_before, a_before, h_after, a_after


def git_commit_push(days, h_del, a_del, size_before, size_after, no_push):
    msg = (f"chore: 清理 {days} 天前历史数据并入库 "
           f"(tag_history 删 {h_del} 行, tag_aggregate 删 {a_del} 行, "
           f"DB {size_before:.1f}MB→{size_after:.1f}MB)")
    rc, _, _ = sh(f'git add backend/modbus_platform.db', check=False)
    if rc != 0:
        log("git add 失败。"); return False
    rc, out, _ = sh(f'git commit -m "{msg}"', check=False)
    if rc != 0:
        # 可能已经是最新
        log("git commit 未产生提交（可能无变化）。")
        return False
    log("已提交: " + msg)
    if no_push:
        log("已跳过 push（--no-push）。")
        return True
    branch = current_branch()
    rc, _, err = sh(f"git push origin {branch}", check=False)
    if rc != 0:
        log("git push 失败，请检查网络 / SSH key。")
        return False
    log(f"已推送到 origin/{branch}。")
    return True


def main():
    ap = argparse.ArgumentParser(description="清理 N 天前历史数据并提交推送数据库")
    ap.add_argument("--days", type=int, default=RETENTION_DAYS, help="保留最近几天（默认 1）")
    ap.add_argument("--no-restart", action="store_true", help="清理后不重启后端")
    ap.add_argument("--no-push", action="store_true", help="只清理+提交，不推送")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要删除的行数，不实际执行")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        log(f"未找到数据库: {DB_PATH}")
        sys.exit(1)

    log(f"目标库: {DB_PATH}（{db_size_mb():.2f} MB）")
    log(f"保留最近 {args.days} 天数据；dry_run={args.dry_run}")

    if not args.dry_run:
        stop_backend()

    size_before = db_size_mb()
    h_before, a_before, h_after, a_after = clean_and_vacuum(args.days, args.dry_run)
    size_after = db_size_mb()

    if not args.dry_run:
        git_commit_push(args.days, h_before - h_after, a_before - a_after,
                        size_before, size_after, args.no_push)
        if not args.no_restart:
            start_backend()

    log("完成。")


if __name__ == "__main__":
    main()
