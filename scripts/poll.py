"""
Vidu Studio - 后台轮询下载脚本

由 vidu-studio skill 在提交任务后通过 run_in_background 启动。
职责：读取 pending_tasks.json → 轮询 Vidu API → 下载完成图片 → 更新状态和 meta.json。

用法：
    python scripts/poll.py

并发安全：
- 文件锁（FileLock）保护所有读-改-写
- PID 文件防止重复启动
- downloading_since 超时重置防止卡死
"""

import os
import sys
import json
import time
import datetime
import subprocess
import requests

# 绕过代理
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    STUDIO_ROOT, TASKS_FILE, TASKS_LOCK_FILE,
    POLL_PID_FILE, POLL_LOG_FILE,
    POLL_INTERVAL, MAX_POLL_TIME,
    DOWNLOADING_TIMEOUT, MAX_CONSECUTIVE_ERRORS,
)


# ─── 日志 ──────────────────────────────────────────────────────────────────────

def log(msg):
    """写入 poll.log 并打印到 stdout"""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(STUDIO_ROOT, exist_ok=True)
        with open(POLL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        # 简单滚动：超过 5MB 则截断保留后半
        if os.path.getsize(POLL_LOG_FILE) > 5 * 1024 * 1024:
            with open(POLL_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(POLL_LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[len(lines) // 2:])
    except OSError:
        pass


# ─── 文件锁（与 submit.py 共用同一把锁）──────────────────────────────────────

class FileLock:
    def __init__(self, lock_path, timeout=10, retry_interval=0.05):
        self.lock_path = lock_path
        self.timeout = timeout
        self.retry_interval = retry_interval
        self._fd = None

    def acquire(self):
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                self._fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                os.write(self._fd, str(os.getpid()).encode())
                return True
            except FileExistsError:
                time.sleep(self.retry_interval)
        raise TimeoutError(f"无法获取文件锁：{self.lock_path}（超时 {self.timeout}s）")

    def release(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_):
        self.release()


# ─── PID 文件 ──────────────────────────────────────────────────────────────────

def acquire_pid():
    """
    尝试写入 PID 文件。如果已有活跃实例，返回 False（本进程应退出）。
    """
    os.makedirs(STUDIO_ROOT, exist_ok=True)
    if os.path.exists(POLL_PID_FILE):
        try:
            with open(POLL_PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, old_pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return False  # 已有活跃实例
        except Exception:
            pass  # PID 文件损坏或进程已死，继续
    with open(POLL_PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_pid():
    try:
        os.remove(POLL_PID_FILE)
    except OSError:
        pass


# ─── 任务文件 I/O ──────────────────────────────────────────────────────────────

def load_tasks():
    if not os.path.exists(TASKS_FILE):
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tasks_locked():
    """在文件锁保护下读取 pending_tasks.json"""
    with FileLock(TASKS_LOCK_FILE):
        return load_tasks()


# ─── meta.json ─────────────────────────────────────────────────────────────────

def load_meta(project, category, name):
    meta_path = os.path.join(STUDIO_ROOT, project, category, name, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_meta(project, category, name, meta):
    item_dir = os.path.join(STUDIO_ROOT, project, category, name)
    os.makedirs(item_dir, exist_ok=True)
    meta_path = os.path.join(item_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def update_meta_on_complete(project, category, name, filename, prompt, original_prompt):
    """下载完成后更新 meta.json，primary_image 始终指向最新版本"""
    meta = load_meta(project, category, name) or {}

    if not meta.get("name"):
        meta = {
            "name": name,
            "category": category,
            "description": original_prompt,
            "prompts": {
                "original": original_prompt,
                "optimized": prompt,
            },
            "images": [],
            "primary_image": None,
            "tags": [],
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
        }

    if filename not in meta.get("images", []):
        meta.setdefault("images", []).append(filename)

    meta["primary_image"] = filename
    meta["updated_at"] = datetime.datetime.now().isoformat()
    save_meta(project, category, name, meta)
    return meta


# ─── 版本号（下载时确定）──────────────────────────────────────────────────────

def resolve_filename(project, category, name, intended_filename):
    """
    下载前再次扫描目录，确保文件名唯一。
    如果意向文件名已存在（另一个任务先落盘），自动递增版本号。
    """
    item_dir = os.path.join(STUDIO_ROOT, project, category, name)
    if not os.path.exists(item_dir):
        return intended_filename

    if "." in intended_filename:
        _, ext = intended_filename.rsplit(".", 1)
    else:
        ext = "png"

    base = name
    existing = set(os.listdir(item_dir))
    if intended_filename not in existing:
        return intended_filename

    max_v = 1
    for f in existing:
        if f == f"{base}.{ext}":
            max_v = max(max_v, 1)
        elif f.startswith(f"{base}_v") and f.endswith(f".{ext}"):
            try:
                v = int(f[len(base) + 2: -len(ext) - 1])
                max_v = max(max_v, v)
            except ValueError:
                pass

    return f"{base}_v{max_v + 1}.{ext}"


# ─── Vidu API 查询 ─────────────────────────────────────────────────────────────

def query_task(api_key, task_id):
    """查询任务状态，返回 (state, creations, err_msg)"""
    url = f"https://api.vidu.cn/ent/v2/tasks/{task_id}/creations"
    headers = {"Authorization": f"Token {api_key}"}
    try:
        resp = requests.get(
            url, headers=headers, timeout=30,
            proxies={"http": None, "https": None}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("state", "unknown"), data.get("creations", []), data.get("err_code")
    except Exception as e:
        return "query_error", [], str(e)


# ─── 图片下载 ──────────────────────────────────────────────────────────────────

def download_image(url, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    resp = requests.get(
        url, timeout=120, stream=True,
        proxies={"http": None, "https": None}
    )
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)


# ─── Windows 系统通知 ──────────────────────────────────────────────────────────

def notify(title, message):
    """通过 PowerShell Windows Runtime API 发送系统通知"""
    # 转义单引号防止 PS 注入
    title = title.replace("'", "\\'")
    message = message.replace("'", "\\'")
    ps_script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null; "
        "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        f"$template.GetElementsByTagName('text')[0].AppendChild($template.CreateTextNode('{title}')) | Out-Null; "
        f"$template.GetElementsByTagName('text')[1].AppendChild($template.CreateTextNode('{message}')) | Out-Null; "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Vidu Studio').Show($template)"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, timeout=10
        )
    except Exception:
        pass


# ─── 超时判断 ──────────────────────────────────────────────────────────────────

def is_wall_clock_timeout(task):
    """基于 created_at 墙钟时间判断任务是否超时"""
    created_at = task.get("created_at")
    if not created_at:
        return False
    try:
        created = datetime.datetime.fromisoformat(created_at)
        elapsed = (datetime.datetime.now() - created).total_seconds()
        return elapsed >= MAX_POLL_TIME
    except Exception:
        return False


def is_downloading_stuck(task):
    """检查 downloading 状态是否卡死超过 DOWNLOADING_TIMEOUT"""
    since = task.get("downloading_since")
    if not since:
        return False
    try:
        t = datetime.datetime.fromisoformat(since)
        elapsed = (datetime.datetime.now() - t).total_seconds()
        return elapsed >= DOWNLOADING_TIMEOUT
    except Exception:
        return False


# ─── 原子合并写入 ──────────────────────────────────────────────────────────────

def merge_and_save(updated_tasks):
    """
    加锁读取最新 pending_tasks.json，用本轮处理结果合并后原子写入。
    保留 submit.py 在本轮处理期间新增的任务。
    """
    with FileLock(TASKS_LOCK_FILE):
        current = load_tasks()
        updated_map = {t["task_id"]: t for t in updated_tasks}
        merged = []
        seen = set()
        for t in current:
            tid = t["task_id"]
            merged.append(updated_map.get(tid, t))
            seen.add(tid)
        # 本轮处理中完全新增的（不太可能，但防御性保留）
        for t in updated_tasks:
            if t["task_id"] not in seen:
                merged.append(t)
        tmp = TASKS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        os.replace(tmp, TASKS_FILE)


# ─── 主循环 ────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("VIDU_API_KEY", "").strip()
    if not api_key:
        print("[poll] VIDU_API_KEY 未设置，退出")
        sys.exit(1)

    if not acquire_pid():
        print("[poll] 已有运行中的实例，退出")
        sys.exit(0)

    log(f"启动，监控 {TASKS_FILE}")

    consecutive_errors = 0
    backoff = POLL_INTERVAL

    try:
        while True:
            try:
                tasks = load_tasks_locked()
            except Exception as e:
                log(f"读取任务文件失败：{e}")
                time.sleep(POLL_INTERVAL)
                continue

            pending_count = sum(
                1 for t in tasks if t.get("status") not in ("completed", "failed")
            )
            if pending_count == 0:
                log("所有任务处理完毕，退出")
                break

            changed = False

            for task in tasks:
                status = task.get("status", "")

                if status in ("completed", "failed"):
                    continue

                # downloading 卡死检测
                if status == "downloading":
                    if is_downloading_stuck(task):
                        log(f"downloading 超时重置：{task['name']} ({task['task_id']})")
                        task["status"] = "pending"
                        task["downloading_since"] = None
                        changed = True
                    continue

                # 墙钟超时（query_error 期间不累加，直接用 created_at）
                if is_wall_clock_timeout(task):
                    task["status"] = "failed"
                    task["error_message"] = f"超时（超过 {MAX_POLL_TIME} 秒）"
                    task["completed_at"] = datetime.datetime.now().isoformat()
                    log(f"超时失败：{task['name']} ({task['task_id']})")
                    changed = True
                    continue

                tid = task["task_id"]
                state, creations, err = query_task(api_key, tid)

                if state == "query_error":
                    consecutive_errors += 1
                    log(f"查询出错（{consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}）：{task['name']} - {err}")
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        backoff = min(backoff * 2, 300)
                        log(f"连续错误达上限，退避 {backoff}s")
                    continue
                else:
                    consecutive_errors = 0
                    backoff = POLL_INTERVAL

                if state == "success" and creations:
                    img_url = creations[0].get("url", "")
                    if not img_url:
                        task["status"] = "failed"
                        task["error_message"] = "API 返回成功但无图片 URL"
                        task["completed_at"] = datetime.datetime.now().isoformat()
                        log(f"无图片URL：{task['name']}")
                        changed = True
                        continue

                    # 下载前确认最终文件名（防版本号竞态）
                    final_filename = resolve_filename(
                        task["project"], task["category"],
                        task["name"], task["filename"]
                    )
                    final_output_path = os.path.join(
                        task["project"], task["category"],
                        task["name"], final_filename
                    )

                    # 标记 downloading，记录时间戳，立即写入（加锁）
                    task["status"] = "downloading"
                    task["downloading_since"] = datetime.datetime.now().isoformat()
                    task["filename"] = final_filename
                    task["output_path"] = final_output_path
                    merge_and_save(tasks)

                    abs_output = os.path.join(STUDIO_ROOT, final_output_path)
                    try:
                        download_image(img_url, abs_output)

                        task["status"] = "completed"
                        task["downloading_since"] = None
                        task["completed_at"] = datetime.datetime.now().isoformat()

                        update_meta_on_complete(
                            task["project"], task["category"], task["name"],
                            final_filename, task["prompt"], task["original_prompt"],
                        )

                        log(f"完成：{task['name']} → {final_output_path}")
                        notify("Vidu Studio", f"{task['name']} 已生成完成")

                    except Exception as e:
                        task["status"] = "failed"
                        task["error_message"] = f"下载失败：{e}"
                        task["downloading_since"] = None
                        task["completed_at"] = datetime.datetime.now().isoformat()
                        log(f"下载失败：{task['name']} - {e}")

                    changed = True

                elif state == "failed":
                    reason = err or "Vidu 生成失败"
                    task["status"] = "failed"
                    task["error_message"] = reason
                    task["completed_at"] = datetime.datetime.now().isoformat()
                    log(f"生成失败：{task['name']} - {reason}")
                    changed = True

            if changed:
                merge_and_save(tasks)

            time.sleep(backoff)

    finally:
        release_pid()
        log("退出")


if __name__ == "__main__":
    main()
