"""
Vidu Studio - 共享配置
所有路径常量集中在此，poll.py 和 submit.py 统一从这里 import。
"""

import os

# 工作目录根
STUDIO_ROOT = os.path.join(os.path.expanduser("~"), "Desktop", "vidu_studio")

# 任务索引文件
TASKS_FILE = os.path.join(STUDIO_ROOT, "pending_tasks.json")

# 文件锁（保护 pending_tasks.json 的读-改-写）
TASKS_LOCK_FILE = os.path.join(STUDIO_ROOT, "pending_tasks.lock")

# PID 文件（防止 poll.py 重复启动）
POLL_PID_FILE = os.path.join(STUDIO_ROOT, "poll.pid")

# 当前激活项目
CURRENT_PROJECT_FILE = os.path.join(STUDIO_ROOT, "current_project.json")

# poll.py 日志
POLL_LOG_FILE = os.path.join(STUDIO_ROOT, "poll.log")

# 轮询参数
POLL_INTERVAL = 8          # 秒，轮询间隔
MAX_POLL_TIME = 600        # 秒，任务从创建到超时的最大墙钟时间
DOWNLOADING_TIMEOUT = 120  # 秒，downloading 状态超时重置阈值
MAX_CONSECUTIVE_ERRORS = 5 # 连续查询错误次数上限，触发指数退避
