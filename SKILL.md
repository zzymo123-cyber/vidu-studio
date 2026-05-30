---
name: vidu-studio
description: Manages a Vidu image generation studio with character, scene/prop, storyboard, and other image libraries. Handles pure-text and reference-image generation, batch submission, and background polling. Use when the user mentions Vidu, creating characters/scenes/storyboards, checking image results, generating images with references, or managing image assets.
---

# Vidu Studio - 图片生成工作室

基于 Vidu API 的图片生成工具，四大分类管理，提交即返回，后台脚本轮询下载，支持纯文生图、参考图生图、批量生成和分类模板填充。

## 核心架构

```
用户交互（我负责）                      后台脚本（poll.py 负责）
─────────────────                      ─────────────────────
1. 填充提示词模板                          持续轮询 pending_tasks.json
2. 确认后调用 submit.py（stdin JSON）     查 Vidu API 状态
3. submit.py 提交 API + 写任务记录        完成的 → 下载到目标路径
4. 确认 poll.py 在跑（PID 文件检查）      更新 status 为 completed
5. 立即返回，继续交互                      发送 Windows 系统通知
                                          跑完所有 pending 后退出
```

**关键原则**：提交即返回，我永远不被轮询阻塞。你随时可以继续提新任务或聊天。

### 脚本文件

| 文件 | 职责 |
|------|------|
| `scripts/config.py` | 路径常量、轮询参数，所有脚本统一 import |
| `scripts/submit.py` | 接收 stdin JSON → 调用 Vidu API → 写 pending_tasks.json（加锁）|
| `scripts/poll.py` | 后台轮询 → 下载图片 → 更新 meta.json → 发送系统通知 |

---

## 素材四分类

| 分类 | 目录名 | 内容示例 |
|------|--------|----------|
| 角色 | `characters/` | 人物、角色设定图 |
| 场景与道具 | `scenes_props/` | 环境、背景、物品、道具 |
| 故事板 | `storyboards/` | 分镜、叙事帧 |
| 其他 | `others/` | 不属于以上三类的图 |

---

## 目录结构与命名规则

**一个图只存一份，路径即唯一地址。重做时自动递增版本号，不覆盖原图。**

```
~/Desktop/vidu_studio/
├── current_project.json           # 当前激活项目（持久化）
├── pending_tasks.json             # 全局任务索引（跨项目）
├── 西游记/                        # 项目目录
│   ├── characters/                # 角色
│   │   └── 孙悟空/
│   │       ├── meta.json
│   │       ├── 孙悟空.png         # v1（首次生成）
│   │       └── 孙悟空_v2.png      # 第一次重做
│   ├── scenes_props/              # 场景与道具
│   │   └── 花果山/
│   │       ├── meta.json
│   │       └── 花果山.png
│   ├── storyboards/               # 故事板
│   │   └── 大闹天宫/
│   │       ├── meta.json
│   │       └── 大闹天宫.png
│   └── others/                    # 其他
└── 三体/                          # 另一个项目
    ├── characters/
    ...
```

**命名规则**：
- 目录名 = 用户取名
- 首次生成：`取名.png`（无版本号）
- 重做版本：`取名_v2.png`、`取名_v3.png`（依此类推）
- `meta.json` 的 `primary_image` 始终指向最新版本
- 路径确定性：`{项目名}/{分类}/{取名}/{取名}.png`

---

## 参考图引用顺序

当从素材库选参考图组合生成时，**固定顺序**：

```
images 数组中的顺序：
1. 角色图（characters）  → 提示词中用"图片1"
2. 道具图（scenes_props）→ 提示词中用"图片2"、"图片3"...
3. 场景图（scenes_props）→ 提示词中用"图片N"
```

提示词优化时自动按此顺序写引用，用户无需手动编号。

---

## 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | 否 | `create_character` / `create_scene_prop` / `create_storyboard` / `generate_image` / `list` / `check_results` / `view` / `new_project` / `switch_project`，默认根据输入自动判断 |
| prompt | string | 是 | 描述文本 |
| images | file[] / url[] | 否 | 额外参考图（本地路径或 URL） |
| character | string / string[] | 否 | 从角色库选取角色名（主图作参考图，排在 images 最前） |
| scene_prop | string / string[] | 否 | 从场景-道具库选取名称（主图作参考图，排在角色图之后） |
| name | string | 否 | 素材取名（角色名/场景名/故事板名等） |
| category | string | 否 | 分类：`characters` / `scenes_props` / `storyboards` / `others` |
| project | string | 否 | 项目名，默认使用当前激活项目 |
| ratio | string | 否 | 画面比例，默认询问用户确认 |
| model | string | 否 | Vidu 模型，默认 `viduimage-2` |
| resolution | string | 否 | 分辨率（1K/2K/3K），默认 `2K` |
| quality | string | 否 | 质量（low/medium/high），默认 `high` |

---

## 意图路由

```
用户说了什么？
├── "创建角色" / "新建角色" → create_character
├── "创建场景" / "创建道具" / "新建场景" → create_scene_prop
├── "创建故事板" / "新建分镜" → create_storyboard
├── "生成图片" / "画一张" → generate_image
├── "查结果" / "查一下" / "图片好了吗" → check_results
├── "查看角色库" / "列出角色" / "有哪些角色" → list
├── "查看XX详情" → view
├── "新建项目" / "创建项目" → new_project
├── "切换项目" / "换到XX项目" → switch_project
├── "转视频提示词" / "生视频提示词" / "把XX故事板转成视频" → storyboard_to_video_prompt
└── 直接描述画面 → 自动判断
    ├── 描述人物/角色 → create_character
    ├── 描述环境/道具 → create_scene_prop
    └── 其他 → generate_image
```

---

## 环境检查

每次执行前检查：

```bash
echo %VIDU_API_KEY%
```

未设置则提示：

```
需要设置环境变量：
- VIDU_API_KEY: Vidu API Key
  获取地址：https://api.vidu.cn
```

---

## 项目管理

### current_project.json 结构

位置：`~/Desktop/vidu_studio/current_project.json`

```json
{
  "current_project": "西游记",
  "updated_at": "2025-05-25T14:30:00"
}
```

### 激活项目逻辑

```
每次执行操作前：
1. 读取 current_project.json
2. 如果有激活项目 → 继续，在标题行提示"当前项目：{项目名}"
3. 如果没有激活项目（文件不存在或为空）：
   a. 扫描 vidu_studio/ 下的项目目录
   b. 如果有已有项目 → 列出让用户选择或新建
   c. 如果没有任何项目 → 直接询问新项目名
4. 确认后写入 current_project.json，会话内记住
```

### 工作流：新建项目

```
用户：新建项目 / 创建项目
Skill：项目名是什么？
用户：西游记
Skill：
1. 创建目录 vidu_studio/西游记/（含四个子目录）
2. 写入 current_project.json
3. ✅ 项目"西游记"已创建并激活
   目录：~/Desktop/vidu_studio/西游记/
```

### 工作流：切换项目

```
用户：切换到三体 / 换项目
Skill：
1. 扫描已有项目列表
2. 列出：
   1. 西游记（当前）
   2. 三体
   3. 新建项目...
用户：选 2
3. 更新 current_project.json → "三体"
4. ✅ 已切换到项目"三体"
```

---

## pending_tasks.json 结构

```json
[
  {
    "task_id": "abc123",
    "project": "西游记",
    "prompt": "优化后的提示词...",
    "original_prompt": "用户原始描述",
    "category": "characters",
    "name": "红袖",
    "filename": "红袖.png",
    "output_path": "西游记/characters/红袖/红袖.png",
    "image_paths": ["/Users/boomer/Desktop/vidu_studio/西游记/characters/红袖/红袖.png"],
    "model": "viduimage-2",
    "ratio": "3:4",
    "resolution": "2K",
    "quality": "high",
    "status": "pending",
    "error_message": null,
    "downloading_since": null,
    "created_at": "2025-05-25T14:30:00",
    "completed_at": null
  }
]
```

**status 取值**：`pending` → `downloading` → `completed` / `failed`

**image_paths**：存原始本地绝对路径（非 base64），submit.py 提交时临时转换，不持久化 base64。

**error_message**：失败原因，"查结果"时直接展示给用户。

**downloading_since**：标记 downloading 的时间戳，超过 120 秒未完成则 poll.py 自动重置为 pending。

---

## meta.json 结构

所有分类统一格式：

```json
{
  "name": "取名",
  "category": "characters",
  "description": "文字描述",
  "prompts": {
    "original": "用户原始描述",
    "optimized": "优化后的生图提示词"
  },
  "images": ["红袖.png"],
  "primary_image": "红袖.png",
  "tags": ["女性", "古风"],
  "created_at": "2025-05-25T14:30:00",
  "updated_at": "2025-05-25T14:30:00"
}
```

---

## 工作流：生图（所有分类通用）

无论创建角色、场景、故事板还是其他，核心流程一致：

```
1. 检查环境（VIDU_API_KEY）
2. 确认分类和取名
3. 收集描述 + 参考图来源
   ├── 用户直接提供的图片（images 参数）
   ├── 从角色库选取（character 参数）
   └── 从场景-道具库选取（scene_prop 参数）
4. 按固定顺序合并参考图路径：角色 → 道具 → 场景 → 额外图片
5. 根据分类选用对应提示词模板，填充用户描述信息
   └── 展示完整提示词，等待用户确认
   └── 模板详情见 references/prompt_templates.md
6. 确认画面比例
7. 通过 submit.py 提交任务：
   echo '<JSON>' | python ~/.qoder/skills/vidu-studio/scripts/submit.py
   JSON 字段：api_key、project、category、name、prompt、original_prompt、
             image_paths（原始路径列表，非 base64）、model、ratio、resolution、quality
   → 成功返回 {"ok": true, "task_id": "...", "output_path": "..."}
   → 失败返回 {"ok": false, "error": "..."}，展示错误给用户
8. 如果是故事板：同步将 panels（9格动作描述）写入 meta.json
9. 检查 poll.py 是否在跑（读 poll.pid 文件）：
   └── 未在跑 → run_in_background 启动：python ~/.qoder/skills/vidu-studio/scripts/poll.py
   └── 已在跑 → 不重复启动，poll.py 下轮自动捡起新任务（最多 8 秒延迟）
10. 立即返回：告知 task_id、目标路径
```

### 关键：提交即返回

第 7-10 步在几秒内完成，之后我立即可以继续交互。轮询下载由 poll.py 在后台处理。

---

## 工作流：查结果

```
用户：查结果 / 图片好了吗

1. 读取当前激活项目（current_project.json）
2. 读取 pending_tasks.json，过滤出当前项目的任务
3. 同时读取各素材目录的 meta.json，补充已完成条目信息
4. 合并展示（pending_tasks.json 为状态主源，meta.json 补充描述和标签）：

当前项目：西游记
| # | 取名 | 分类 | 原始描述 | 状态 | 输出路径 |
|---|------|------|---------|------|----------|
| 1 | 红袖 | 角色 | 古风侠女 | ✅已完成 | 西游记/characters/红袖/红袖.png |
| 2 | 长剑 | 道具 | 古风长剑 | ⏳生成中 | 西游记/scenes_props/长剑/长剑.png |
| 3 | 拔剑 | 故事板 | 红袖拔剑 | ❌失败：下载失败：ConnectionError | 西游记/storyboards/拔剑/拔剑.png |

5. 已完成的：图片已保存到对应路径，meta.json 已更新
6. 失败的：展示 error_message 具体原因，询问用户是否重试
```

---

## 工作流：浏览素材库

```
用户：查看角色库 / 列出场景 / 有哪些道具

| # | 取名 | 描述 | 标签 | 图片数 | 创建时间 |
|---|------|------|------|--------|----------|
| 1 | 红袖 | 穿红衣的侠女 | 古风,侠客 | 1 | 2025-05-25 |
```

---

## 工作流：故事板转视频提示词

故事板生成时已经存下了 9 格动作描述（`panels`）和完整生图提示词（`prompts.optimized`）。转视频提示词时复用这些文字，按 v2 结构化镜头格式合成可直接用于视频生成（Seedance 等）的提示词。

**简要步骤**：
1. 读取对应故事板的 `meta.json`
2. 取出 `panels`（9格，每格含 `shot` + `action`）+ `prompts.optimized`
3. 从用户提供剧本中提取台词，按 3字/秒（正常）、2字/秒（耳语）、2.5字/秒（VO）计算时长
4. 按情绪节拍拆分为 2-3 段，每段 10-15 秒
5. 按 v2 格式输出（段头全局声明 + 每格镜头单元含空间/姿态/位置/情绪/散文段）
6. 用户确认后保存到 `meta.json` 的 `video_prompts` 字段

**完整规范、模板和示例见 [references/video_prompt_format.md](references/video_prompt_format.md)。**

---

## 提交任务（调用 submit.py）

```bash
echo '{"api_key":"...","project":"西游记","category":"characters","name":"红袖",
       "prompt":"优化后提示词","original_prompt":"古风侠女",
       "image_paths":["/绝对路径/角色图.png"],
       "model":"viduimage-2","ratio":"3:4","resolution":"2K","quality":"high"}' \
  | python ~/.qoder/skills/vidu-studio/scripts/submit.py
```

**image_paths**：传原始本地绝对路径列表，submit.py 内部转 base64，不在 pending_tasks.json 里存 base64。

成功输出：`{"ok": true, "task_id": "abc123", "output_path": "西游记/characters/红袖/红袖.png", "filename": "红袖.png"}`
失败输出：`{"ok": false, "error": "API 提交失败：..."}`

---

## 后台轮询脚本（poll.py）

位置：`~/.qoder/skills/vidu-studio/scripts/poll.py`

**由我在提交任务后检查 PID 文件，未运行时通过 `run_in_background` 启动。**

脚本职责：
1. 读取 `pending_tasks.json`（加文件锁）
2. 逐个查询 Vidu API 状态（查询出错时指数退避，最长 300 秒）
3. 超时判断基于 `created_at` 墙钟时间（默认 600 秒），poll.py 重启不影响计时
4. 完成的 → 标记 `downloading`（记录 `downloading_since`）→ 下载时确定最终文件名 → 下载 → 标记 `completed` → 更新 meta.json → 发送 Windows 系统通知
5. `downloading` 超过 120 秒未完成 → 重置为 `pending` 重试
6. 失败的 → 标记 `failed`，写入 `error_message`
7. 所有任务终态后退出，删除 PID 文件
8. 运行日志写入 `poll.log`（5MB 自动滚动）

**启动方式**：
```bash
python ~/.qoder/skills/vidu-studio/scripts/poll.py
```

---

## 提示词策略

每个分类使用独立的提示词模板。模板骨架为英文（结构性指令），填入部分为中文（角色/场景描述）。展示给用户确认后再提交。

如果用户说"我自己写好了，直接提交"，则跳过模板，原样提交用户的 prompt。

**三分类完整模板见 [references/prompt_templates.md](references/prompt_templates.md)。**

**模板路由**：
```
分类判定 → 模板选择
├── characters        → 角色设定板
├── scenes_props      → 场景参考板 / 道具参考板（根据描述自动判断）
├── storyboards       → 故事板（必须有参考图）
└── others            → 无模板，直接使用用户 prompt
```

---

## 批量生图

一次提交多张图（如一组故事板分镜）：

```python
def batch_submit(api_key, prompts, original_prompts, category, name, filenames,
                 image_sources_list=None, model="viduimage-2", ratio="16:9", resolution="2K", quality="high"):
    """批量提交，间隔1秒避免限流"""
    task_ids = []
    for i, (prompt, orig) in enumerate(zip(prompts, original_prompts)):
        img_srcs = image_sources_list[i] if image_sources_list else None
        tid = submit_and_record(api_key, prompt, orig, category, name, filenames[i],
                                img_srcs, model, ratio, resolution, quality)
        task_ids.append(tid)
        if i < len(prompts) - 1:
            time.sleep(1)
    return task_ids
```

批量提交后统一启动一次 poll.py 即可。

---

## 失败处理

用户说"查结果"时，如果发现 `failed` 状态：

```
图片生成失败。
取名：{name} | 原因：{reason}
原始提示词：{original_prompt}

请选择：
1. 重试（使用相同提示词重新提交）
2. 修改提示词后重试
3. 换模型重试
4. 放弃
```

---

## 完整交互流程示例

**示例见 [examples.md](examples.md)**，包含：
1. 创建角色（模板填充）
2. 角色+道具组合生故事板（模板填充）
3. 故事板转视频提示词

---

## Vidu 模型与配置参考

**模型表、价格表、默认配置、API 端点详情见 [references/model_reference.md](references/model_reference.md)。**

---

## 注意事项

1. **Vidu 认证格式**：`Authorization: Token {VIDU_API_KEY}`（`Token` 不是 `Bearer`）
2. **viduq1 必须传参考图**：纯文生图只能用 viduq2+
3. **viduimage-2 参考图数量**：支持 0-14 张，但 POST payload 上限 20MB，2K 图片 base64 约 2-4MB，因此 4-5 张 2K 参考图安全
4. **base64 在 submit.py 内部转换**：image_paths 传原始本地路径，submit.py 提交时临时转 base64，pending_tasks.json 不存 base64
5. **参考图固定顺序**：角色 → 道具 → 场景 → 额外图片
6. **提交即返回**：我永远不会阻塞等轮询
7. **poll.py 单实例**：通过 PID 文件（`poll.pid`）保证只有一个实例运行；提交任务前检查 PID 文件，未运行时才通过 `run_in_background` 启动
8. **并发写入安全**：submit.py 和 poll.py 都通过 `pending_tasks.lock` 文件锁保护读-改-写，原子写入（tmp + rename）
9. **画面比例必须确认**：每次生图前询问用户
10. **禁止未经确认调用 API**：模板填充后的完整提示词必须用户确认后才提交
11. **单份存储**：一个图只存一份，路径唯一；重做时递增版本号（_v2/_v3），不覆盖原图
12. **版本号下载时确定**：poll.py 下载前再次扫描目录确认最终文件名，防止快速连续重做时版本号冲突；pending_tasks.json 里的 filename 为意向名
13. **primary_image 始终最新**：poll.py 下载完成后更新 meta.json 的 primary_image 指向最新版本文件名
14. **项目隔离**：所有操作默认在当前激活项目下进行；路径格式 `{项目名}/{分类}/{取名}/{文件名}`
15. **current_project.json 持久化**：每次切换或新建项目后立即写入，下次会话自动恢复
16. **绕过代理**：`NO_PROXY=*` 及 `proxies={"http": None, "https": None}` 避免本地代理拦截
17. **URL 有效期**：Vidu 生成的图片 URL 通常 24h 过期，poll.py 应及时下载
18. **提示词模板语言**：骨架英文 + 填入部分中文
19. **角色图 = 设定板**：角色库里的图是多角度设定板，不是单张立像
20. **故事板必须有参考图**：使用角色+场景作为 Image A/B
21. **角色变体必须传原角色板**：创建同一角色的变体设定板（如换装、不同状态）时，必须将原始角色板作为 Image 1 传入，并在提示词中加入 `CRITICAL: The face must be identical to Image 1`，否则面部不一致
22. **Payload 20MB 上限**：POST body 超 20MB 会返回错误。策略：优先压缩参考图数量，超出时用文字描述替代场景参考图
23. **moderation: disabled**：所有提交必须包含 `"moderation": "disabled"` 参数，否则部分内容可能被误拦截
24. **故事板反 CG 提示词**：故事板提示词必须包含反 CG 约束语言，如 `NOT a game CG screenshot, NOT a 3D render, NOT a digital painting, NOT anime`，并加入 `Modern digital cinema camera, live-action feature film production stills` 以确保真人电影质感
25. **故事板色调一致性**：Master Shot 和故事板的色调描述必须与项目整体风格一致。都市写实项目用 `cool grey-blue, muted naturalistic, modern digital cinema camera, NO film grain, NO vintage look`，不要用 `35mm Kodak film` / `golden hour` / `anamorphic lens` 等会推偏色调的描述
26. **Master Shot 强制前置**：所有故事板生成前必须先生成并确认 Master Shot。Master Shot 存储在对应故事板目录下（如 `storyboards/SB-E2-02家门口清晨江宁告别/master_shot.jpg`），meta.json 里用 `master_shot` 字段记录文件名，可多版本（`master_shot_v2.jpg`）
27. **Master Shot 参考图规则**：传入角色图（所有在场角色）+ 场景图，**不传道具图**（道具局部细节会干扰全景构图）。比例固定 16:9。所有在场角色必须同时出现且全身可见，不能漏人。色调必须与项目一致
28. **Master Shot → 故事板传参**：Master Shot 确认后压缩为 JPG 控制 payload，作为最后一张参考图（Image D/E）传入故事板。提示词声明 `Use Image D as the MASTER SPATIAL REFERENCE`
29. **故事板每格必须写明所有角色位置**：panel 描述里不能只写主角动作，所有在场角色都必须有位置描述，否则模型会省略未提及的角色
30. **身体朝向歧义必须显式声明**：panel 描述里凡涉及人物朝向，必须写 `BACK TO CAMERA` / `facing LEFT` / `facing camera` 等明确方向，不能只写"挥手"、"转头"等动词
31. **查结果合并两个来源**：状态从 pending_tasks.json 读取，失败时展示 error_message 具体原因；meta.json 补充描述和标签信息
32. **超时基于墙钟时间**：任务超时用 created_at 和当前时间做差（默认 600 秒），poll.py 重启不影响计时，query_error 期间不计入超时
