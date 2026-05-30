# Vidu 模型与配置参考

## Vidu 模型参考

| 模型 | 纯文生图 | 参考生图 | 分辨率 | 支持比例 | 参考图数量 |
|------|----------|----------|--------|----------|-----------|
| viduq1 | 不支持 | 支持（必须≥1张图） | 1080p | 16:9, 9:16, 1:1, 3:4, 4:3 | ≤7 |
| viduq2 | 支持 | 支持 | 1080p | 16:9, 9:16, 1:1, 3:4, 4:3, 21:9, 2:3, 3:2 | ≤7 |
| viduimage-2 | 支持 | 支持 | 1K / 2K / 3K | 16:9, 9:16, 1:1, 3:4, 4:3, 7:3, 2:3, 3:2 | 0-14 |

### viduimage-2 7:3 比例参考价格

| 分辨率 | 质量 | 价格（点数） |
|--------|------|-------------|
| 1K | low | 10 |
| 1K | medium | 14 |
| 1K | high | 20 |
| 2K | low | 20 |
| 2K | medium | 28 |
| 2K | high | 40 |
| 3K | low | 40 |
| 3K | medium | 56 |
| 3K | high | 80 |

---

## 默认生成配置

| 分类 | 模型 | 分辨率 | 质量 | 画面比例 |
|------|------|--------|------|----------|
| 角色设定板 | viduimage-2 | 2K | high | 3:4 |
| 场景参考板 | viduimage-2 | 2K | high | 7:3 |
| 道具参考板 | viduimage-2 | 2K | high | 7:3 |
| 故事板 | viduimage-2 | 2K | high | 7:3 |
| 其他 | viduimage-2 | 2K | high | 16:9 |

---

## API 参考

**认证方式**：`Authorization: Token {VIDU_API_KEY}`（注意是 `Token` 不是 `Bearer`）

**API 端点**：
- 生图提交：`https://api.vidu.cn/ent/v2/reference2image`
- 任务查询：`https://api.vidu.cn/ent/v2/tasks/{task_id}/creations`

**绕过代理**：所有 API 调用设置 `proxies={"http": None, "https": None}` 并设 `NO_PROXY=*`。
