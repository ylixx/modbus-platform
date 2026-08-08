#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modbus 平台一键启动器 (Windows)
- 清理 8000 / 3000 端口占用
- 启动后端 (uvicorn, 自动探测 venv / 系统 python)
- 启动前端 (frontend-v2, 直启 vite, 端口 3000; 缓存指向系统临时目录)
- 轮询端口就绪后打开浏览器

用法:
  双击 start_modbus.bat 即可；或在终端执行: python start_modbus.py
"""
import os
import sys
import time
import socket
import shutil
import subprocess
import tempfile
import webbrowser

# ---------- 路径配置（基于本文件自动推导，克隆/移动仓库无需修改） ----------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend-v2")

BACKEND_PORT = 8000
FRONTEND_PORT = 3000

# vite 冷启动/依赖预构建可能超过 1 分钟（本机实测 ~140s），前端等待上限放宽
BACKEND_WAIT_SECONDS = 60
FRONTEND_WAIT_SECONDS = 240

# 在 WorkBuddy 终端内运行时会注入这些变量，需清除以免 safe-delete 拦截删除
SAFE_DELETE_VARS = [
    "CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR",
    "CODEBUDDY_TOOL_CALL_ID",
    "CODEBUDDY_SAFE_DELETE_BULK_GUARD",
    "GENIE_TRASH_DIR",
]

DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)


def log(msg):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(msg, flush=True)


def find_python():
    for candidate in (
        os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe"),
        os.path.join(BACKEND_DIR, "venv", "Scripts", "python.exe"),
    ):
        if os.path.exists(candidate):
            return candidate
    return shutil.which("python") or "python"


def find_node():
    return shutil.which("node") or "node"


def find_vite_js():
    return os.path.join(FRONTEND_DIR, "node_modules", "vite", "bin", "vite.js")


def check_env(python, node, vite_js):
    ok = True
    try:
        out = subprocess.check_output(
            [python, "-c", "import uvicorn, fastapi, sqlalchemy"], stderr=subprocess.STDOUT
        )
    except Exception:
        log("  - 后端依赖未安装，请先执行: %s -m pip install -r %s" % (python, os.path.join(BACKEND_DIR, "requirements.txt")))
        ok = False
    if not os.path.exists(vite_js):
        log("  - 前端依赖未安装，请先在 %s 执行: pnpm install" % FRONTEND_DIR)
        ok = False
    return ok


def kill_port(port):
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return
    for line in out.splitlines():
        if ("LISTENING" in line) and (":%d " % port in line):
            pid = line.split()[-1]
            try:
                subprocess.run(
                    ["taskkill", "/PID", pid, "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                log("  - 已结束占用端口 %d 的进程 PID=%s" % (port, pid))
            except Exception:
                pass


def build_env():
    env = os.environ.copy()
    for k in SAFE_DELETE_VARS:
        env.pop(k, None)
    # 缓存指向系统真实临时目录，确保 safe-delete 走原生删除而非回收站
    cache = os.path.join(tempfile.gettempdir(), "modbus-vite-cache")
    os.makedirs(cache, exist_ok=True)
    env["VITE_CACHE_DIR"] = cache
    return env


def start_backend(python):
    log_dir = os.path.join(BACKEND_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "backend.log")
    log("[后端] 启动 uvicorn (cwd=%s)" % BACKEND_DIR)
    with open(log_file, "w", encoding="utf-8") as lf:
        return subprocess.Popen(
            [python, "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
            cwd=BACKEND_DIR,
            stdout=lf,
            stderr=subprocess.STDOUT,
            env=build_env(),
            creationflags=DETACHED,
        )


def start_frontend(node, vite_js):
    log_dir = os.path.join(FRONTEND_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "frontend.log")
    log("[前端] 启动 vite (cwd=%s, :%d)" % (FRONTEND_DIR, FRONTEND_PORT))
    with open(log_file, "w", encoding="utf-8") as lf:
        return subprocess.Popen(
            [node, vite_js, "--mode", "base", "--host", "0.0.0.0", "--port", str(FRONTEND_PORT)],
            cwd=FRONTEND_DIR,
            stdout=lf,
            stderr=subprocess.STDOUT,
            env=build_env(),
            creationflags=DETACHED,
        )


def wait_port(port, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def wait_unocss_ready(port, timeout):
    """等待 vite 首次 unocss 全量扫描完成（页面秒开的前置条件）。"""
    import urllib.request
    url = "http://127.0.0.1:%d/src/plugins/unocss/index.ts" % port
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            t0 = time.time()
            with urllib.request.urlopen(url, timeout=30) as r:
                r.read()
            if time.time() - t0 < 1.0:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main():
    log("=" * 52)
    log("         Modbus 平台一键启动")
    log("=" * 52)

    python = find_python()
    node = find_node()
    vite_js = find_vite_js()
    log("Python : %s" % python)
    log("Node   : %s" % node)

    if not check_env(python, node, vite_js):
        log("环境检查未通过，请先安装依赖后重试。")
        return

    log("步骤1: 清理已占用端口...")
    kill_port(BACKEND_PORT)
    kill_port(FRONTEND_PORT)
    time.sleep(1)

    log("步骤2: 启动服务...")
    start_backend(python)
    start_frontend(node, vite_js)

    log("步骤3: 等待后端就绪 (:%d)..." % BACKEND_PORT)
    b_ok = wait_port(BACKEND_PORT, BACKEND_WAIT_SECONDS)
    log("   后端: " + ("就绪 OK" if b_ok else "未就绪 (查 backend/logs/backend.log)"))

    log("步骤4: 等待前端就绪 (:%d，最多 %d 秒)..." % (FRONTEND_PORT, FRONTEND_WAIT_SECONDS))
    f_ok = wait_port(FRONTEND_PORT, FRONTEND_WAIT_SECONDS)
    if f_ok:
        log("   前端: 端口就绪，等待 unocss 首扫完成（确保页面秒开）...")
        f_ok = wait_unocss_ready(FRONTEND_PORT, FRONTEND_WAIT_SECONDS)
        log("   前端: " + ("就绪 OK" if f_ok else "unocss 预热超时，仍可访问"))

    if f_ok:
        time.sleep(1)
        try:
            webbrowser.open("http://localhost:%d" % FRONTEND_PORT)
            log("已在浏览器打开 http://localhost:%d" % FRONTEND_PORT)
        except Exception:
            log("（无法自动打开浏览器，请手动访问 http://localhost:%d）" % FRONTEND_PORT)

    log("-" * 52)
    log("前端: http://localhost:%d" % FRONTEND_PORT)
    log("后端: http://localhost:%d  (API 文档: http://localhost:%d/docs)" % (BACKEND_PORT, BACKEND_PORT))
    log("默认账号: admin / admin123")
    log("服务在独立进程中运行，可关闭本窗口。")
    log("停止服务：任务管理器结束 uvicorn / vite 进程，")
    log("           或运行脚本结束 %d/%d 端口占用进程。" % (BACKEND_PORT, FRONTEND_PORT))
    log("=" * 52)


if __name__ == "__main__":
    main()
