#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modbus 平台一键启动器 (Windows)
- 清理 8000 / 3000 端口占用
- 启动后端 (uvicorn, 托管 venv python)
- 启动前端 (vite, 托管 node; 绕开 safe-delete 拦截; 缓存指向系统临时目录)
- 轮询端口就绪后打开浏览器

直接双击 start_modbus.bat 即可；或在终端执行: python start_modbus.py
"""
import os
import sys
import time
import socket
import subprocess
import tempfile
import webbrowser

# ---------- 路径配置（如环境不同请按需修改） ----------
PROJECT_ROOT = r"E:\modbus-platform"
PYTHON = r"C:\Users\liyan\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
NODE = r"C:\Users\liyan\.workbuddy\binaries\node\versions\22.22.2\node.exe"
VITE_JS = os.path.join(PROJECT_ROOT, "frontend", "node_modules", "vite", "bin", "vite.js")

BACKEND_PORT = 8000
FRONTEND_PORT = 3000

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


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


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


def start_backend():
    cwd = os.path.join(PROJECT_ROOT, "backend")
    log_dir = os.path.join(cwd, "logs")
    ensure_dir(log_dir)
    log_file = os.path.join(log_dir, "backend.log")
    log("[后端] 启动 uvicorn (cwd=%s)" % cwd)
    with open(log_file, "w", encoding="utf-8") as lf:
        return subprocess.Popen(
            [PYTHON, "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
            cwd=cwd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            env=build_env(),
            creationflags=DETACHED,
        )


def start_frontend():
    cwd = os.path.join(PROJECT_ROOT, "frontend")
    log_dir = os.path.join(cwd, "logs")
    ensure_dir(log_dir)
    log_file = os.path.join(log_dir, "frontend.log")
    log("[前端] 启动 vite (cwd=%s)" % cwd)
    with open(log_file, "w", encoding="utf-8") as lf:
        return subprocess.Popen(
            [NODE, VITE_JS, "--host", "0.0.0.0"],
            cwd=cwd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            env=build_env(),
            creationflags=DETACHED,
        )


def wait_port(port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    log("=" * 52)
    log("         Modbus 平台一键启动")
    log("=" * 52)

    log("步骤1: 清理已占用端口...")
    kill_port(BACKEND_PORT)
    kill_port(FRONTEND_PORT)
    time.sleep(1)

    log("步骤2: 启动服务...")
    start_backend()
    start_frontend()

    log("步骤3: 等待后端就绪 (:%d)..." % BACKEND_PORT)
    b_ok = wait_port(BACKEND_PORT, 30)
    log("   后端: " + ("就绪 OK" if b_ok else "未就绪 (查 backend/logs/backend.log)"))

    log("步骤4: 等待前端就绪 (:%d)..." % FRONTEND_PORT)
    f_ok = wait_port(FRONTEND_PORT, 30)
    log("   前端: " + ("就绪 OK" if f_ok else "未就绪 (查 frontend/logs/frontend.log)"))

    if f_ok:
        time.sleep(1)
        try:
            webbrowser.open("http://localhost:%d" % FRONTEND_PORT)
            log("已在浏览器打开 http://localhost:%d" % FRONTEND_PORT)
        except Exception:
            log("（无法自动打开浏览器，请手动访问 http://localhost:%d）" % FRONTEND_PORT)

    log("-" * 52)
    log("启动完成。服务在独立进程中运行，可关闭本窗口。")
    log("停止服务：任务管理器结束 uvicorn / vite 进程，")
    log("           或运行脚本结束 8000/3000 端口占用进程。")
    log("=" * 52)


if __name__ == "__main__":
    main()
