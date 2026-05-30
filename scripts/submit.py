"""
Vidu Studio - 任务提交脚本

由 vidu-studio skill 通过 Bash 调用：
    echo '<JSON>' | python scripts/submit.py

stdin JSON 字段：
    api_key        str   必填  Vidu API Key
    project        str   必填  项目名
    category       str   必填  characters / scenes_props / storyboards / others
    name           str   必填  素材取名
    prompt         str   必填  优化后的生图提示词
    original_prompt str  必填  用户原始描述
    image_paths    list  选填  参考图的本地绝对路径列表（不传 base64，这里转换）
    model          str   选填  默认 viduimage-2
    ratio          str   选填  默认 16:9
    resolution     str   选填  默认 2K
    quality        str   选填  默认 high

stdout：提交成功输出 JSON {"ok": true, "task_id": "...", "output_path": "..."}
        提交失败输出 JSON {"ok": false, "error": "..."}
"""

import os
import sys
import json
import base64
import datetime
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 绕过代理
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

# 把 skill 目录加入路径，确保能 import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    STUDIO_ROOT, TASKS_FILE, TASKS_LOCK_FILE,
    POLL_PID_FILE, POLL_INTERVAL,
)


# ─── 文件锁 ────────────────────────────────────────────────────────────────────

class FileLock:
    """
    跨平台文件锁，保护 pending_tasks.json 的读-改-写。
    使用独占创建（O_CREAT | O_EXCL）实现原子加锁，轮询等待。
    """
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


# ─── 图片工具 ──────────────────────────────────────────────────────────────────

def img_to_data_uri(path):
    """本地文件转 base64 data URI"""
    ext = path.rsplit(".", 1)[-1].lower()
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }.get(ext, "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def prepare_image_sources(image_paths):
    """
    将图片路径列表转为 Vidu API 接受的格式：
    - http/https 开头 → 直接使用 URL
    - 否则 → 读取本地文件转 base64 data URI
    """
    sources = []
    for path in image_paths:
        if str(path).startswith("http"):
            sources.append(path)
        else:
            sources.append(img_to_data_uri(path))
    return sources


# ─── Vidu API ──────────────────────────────────────────────────────────────────

def _make_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    return session


def vidu_submit(api_key, prompt, image_sources=None,
                aspect_ratio="16:9", model="viduimage-2",
                resolution="2K", quality="high"):
    """
    提交生图任务，返回 task_id。
    image_sources 为 None 或空列表时走纯文生图。
    """
    url = "https://api.vidu.cn/ent/v2/reference2image"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {api_key}",
    }
    body = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "quality": quality,
        "moderation": "disabled",
    }
    if image_sources:
        body["images"] = image_sources[:14]

    session = _make_session()
    resp = session.post(
        url, json=body, headers=headers,
        timeout=180, proxies={"http": None, "https": None}
    )
    resp.raise_for_status()
    task_id = resp.json().get("task_id")
    if not task_id:
        raise ValueError(f"API 未返回 task_id，响应：{resp.text[:200]}")
    return task_id


# ─── 任务记录 ──────────────────────────────────────────────────────────────────

def _next_filename(project, category, name, ext="png"):
    """
    扫描目标目录，确定下一个意向文件名（版本递增）。
    首次：{name}.{ext}
    重做：{name}_v2.{ext}、{name}_v3.{ext} ...
    实际落盘文件名由 poll.py 下载时再次确认，此处为意向名。
    """
    item_dir = os.path.join(STUDIO_ROOT, project, category, name)
    if not os.path.exists(item_dir):
        return f"{name}.{ext}"

    existing = os.listdir(item_dir)
    # 找最大版本号
    max_v = 1
    base = name
    for f in existing:
        if f == f"{base}.{ext}":
            max_v = max(max_v, 1)
        elif f.startswith(f"{base}_v") and f.endswith(f".{ext}"):
            try:
                v = int(f[len(base) + 2: -len(ext) - 1])
                max_v = max(max_v, v)
            except ValueError:
                pass

    # 如果 v1（无后缀）已存在，下一个是 v2
    if f"{base}.{ext}" in existing:
        return f"{base}_v{max_v + 1}.{ext}"
    return f"{base}.{ext}"


def append_task(record):
    """在文件锁保护下，将任务记录追加到 pending_tasks.json"""
    os.makedirs(STUDIO_ROOT, exist_ok=True)
    with FileLock(TASKS_LOCK_FILE):
        tasks = []
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        tasks.append(record)
        # 原子写入：先写临时文件再 rename
        tmp = TASKS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        os.replace(tmp, TASKS_FILE)


# ─── 主逻辑 ────────────────────────────────────────────────────────────────────

def main():
    # 读取 stdin JSON
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"stdin JSON 解析失败：{e}"}))
        sys.exit(1)

    api_key        = payload.get("api_key", "").strip()
    project        = payload.get("project", "").strip()
    category       = payload.get("category", "").strip()
    name           = payload.get("name", "").strip()
    prompt         = payload.get("prompt", "").strip()
    original_prompt= payload.get("original_prompt", "").strip()
    image_paths    = payload.get("image_paths", [])
    model          = payload.get("model", "viduimage-2")
    ratio          = payload.get("ratio", "16:9")
    resolution     = payload.get("resolution", "2K")
    quality        = payload.get("quality", "high")

    # 参数校验
    missing = [k for k, v in [
        ("api_key", api_key), ("project", project), ("category", category),
        ("name", name), ("prompt", prompt), ("original_prompt", original_prompt),
    ] if not v]
    if missing:
        print(json.dumps({"ok": False, "error": f"缺少必填字段：{missing}"}))
        sys.exit(1)

    # 确保目标目录存在
    item_dir = os.path.join(STUDIO_ROOT, project, category, name)
    os.makedirs(item_dir, exist_ok=True)

    # 转换参考图（本地路径 → base64 data URI）
    image_sources = []
    if image_paths:
        try:
            image_sources = prepare_image_sources(image_paths)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"参考图处理失败：{e}"}))
            sys.exit(1)

    # 提交 API
    try:
        task_id = vidu_submit(
            api_key, prompt, image_sources,
            aspect_ratio=ratio, model=model,
            resolution=resolution, quality=quality,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"API 提交失败：{e}"}))
        sys.exit(1)

    # 确定意向文件名（版本递增，poll.py 下载时再次确认）
    filename = _next_filename(project, category, name)
    output_path = os.path.join(project, category, name, filename)

    # 写入 pending_tasks.json（加锁）
    record = {
        "task_id": task_id,
        "project": project,
        "prompt": prompt,
        "original_prompt": original_prompt,
        "category": category,
        "name": name,
        "filename": filename,           # 意向文件名，poll.py 下载时可能递增
        "output_path": output_path,     # 意向路径，同上
        "image_paths": image_paths,     # 原始路径（非 base64）
        "model": model,
        "ratio": ratio,
        "resolution": resolution,
        "quality": quality,
        "status": "pending",
        "error_message": None,
        "downloading_since": None,
        "created_at": datetime.datetime.now().isoformat(),
        "completed_at": None,
    }
    try:
        append_task(record)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"写入任务索引失败：{e}"}))
        sys.exit(1)

    print(json.dumps({
        "ok": True,
        "task_id": task_id,
        "output_path": output_path,
        "filename": filename,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
