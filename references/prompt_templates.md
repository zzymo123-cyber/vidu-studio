# 提示词模板（分类模板）

每个分类使用独立的提示词模板。模板骨架为英文（结构性指令），填入部分为中文（角色/场景描述）。展示给用户确认后再提交。

如果用户说"我自己写好了，直接提交"，则跳过模板，原样提交用户的 prompt。

---

## 模板一：角色设定板（characters）

用户描述角色后，根据描述信息填充以下模板。模板中的 `[填入]` 部分用中文，骨架指令保持英文。

```
请创作一张高完成度的「电影级角色设定板」。

角色名称：[填入名字]
年龄：[填入]
身高：[填入]
体型：[填入]
风格方向：[填入：电影级风格化写实 / 半写实 / 动画电影感 / 东方角色设计等]
性格关键词：[填入3-5个]
外貌特征：[填入：脸型、眼睛、发型、肤色、独特记忆点]
服装设定：[填入：上装、下装、外层、鞋子、配件、道具]
场景气质：[填入：角色属于什么环境 / 职业 / 社会身份]

要求生成一张像影视或动画项目开发用的高级角色提案板，而不是普通三视图。

版面结构必须包含：
1. 一张主视觉角色立像
2. 一组全身多角度转面图（正面、3/4、侧面、背面、3/4背面）
3. 一组头部研究图（正面、3/4、侧面、低头、抬头、动态角度）
4. 一张电影感情绪肖像
5. 一组服装与配件拆解说明
6. 少量专业标注信息（角色名、身高刻度、材质备注、性格关键词）

排版要求：
- 横版大画幅
- 不要规则网格，不要机械对称
- 构图要像美术指导设计过，略带不对称感
- 背景为中性灰或浅灰提案板质感
- 画面高级、清晰、专业、具备电影提案板气质

表现要求：
- 角色像真实演员在镜头中被捕捉，而不是摆拍模特
- 五官、身材比例、发型、服装在所有角度中必须严格一致
- 皮肤、布料、金属、皮革等材质必须真实
- 整张图要有电影感、角色感、故事感和高一致性
```

**填充逻辑**：用户只说简短描述（如"古风侠女"），根据描述推断并补充模板中的所有字段，展示给用户确认。用户也可以主动提供详细信息，直接填入。

---

## 模板二：场景与道具参考板（scenes_props）

### 场景模板

```
Create a cinematic multi-angle scene reference board of one single physical location.

Scene:
[用中文填入：房间类型、布局、主要家具、门的位置、窗的位置、材质、道具、光照方向、时段、氛围]

All four panels must show the exact same physical room from different camera positions only.
Do not create different rooms with a similar style.
Do not redesign the room between panels.

Keep consistent across all panels:
same room layout, same architecture, same wall structure, same door position, same window position, same furniture placement, same floor material, same wall texture, same props, same lighting direction, same color palette, same time of day, same atmosphere, and same spatial scale.

Only change the camera angle.

Create a clean 2x2 reference grid with four panels.
Do not include numbers, labels, captions, titles, or visible text.

Panel arrangement:
top-left: front wide master shot showing the full room layout
top-right: reverse angle from inside the room looking toward the entrance
bottom-left: high-angle top-down view showing spatial relationships and furniture placement
bottom-right: cinematic medium shot focused on the main action area, showing material texture and lighting detail

All panels should look like live-action cinematic production stills with realistic perspective, natural lens behavior, coherent spatial continuity, and consistent lighting.

No text, no watermark, no distorted geometry, no inconsistent furniture placement, no duplicated objects, no extra rooms.
```

### 道具模板

道具复用场景骨架，将"room"替换为"item/object"，4 格展示同一物品的关键角度和细节：

```
Create a cinematic multi-angle reference board of one single physical object.

Object:
[用中文填入：物品名称、材质、尺寸感、颜色、细节特征、使用痕迹、风格方向]

All four panels must show the exact same physical object from different camera positions only.
Do not create different versions of the object.
Do not redesign the object between panels.

Keep consistent across all panels:
same object shape, same material, same color, same texture, same proportions, same detail marks, same wear marks, same lighting direction, same color palette, and same atmosphere.

Only change the camera angle.

Create a clean 2x2 reference grid with four panels.
Do not include numbers, labels, captions, titles, or visible text.

Panel arrangement:
top-left: front master shot showing the full object
top-right: side profile shot showing silhouette and thickness
bottom-left: top-down view showing overall shape and proportions
bottom-right: cinematic hero shot / close-up detail focused on the object's most iconic feature and material texture

All panels should look like live-action cinematic production stills with realistic perspective, natural lens behavior, coherent visual continuity, and consistent lighting.

No text, no watermark, no distorted geometry, no inconsistent details, no duplicated elements.
```

**路由逻辑**：描述环境/地点 → 用场景模板；描述物品/道具 → 用道具模板。

---

## 模板三：故事板（storyboards）

故事板始终使用角色图 + 场景/道具图作为参考图，按固定顺序排列。

### 参考图映射

- Image A = 第一个角色主图
- Image B = 第二个角色主图（如有）
- Image C = 场景/道具主图
- Image D = **Master Shot 空间基准图**（多角色户外/大空间场景时使用，见下方说明）

### Master Shot 强制前置流程

**所有故事板**生成前必须先生成并确认 Master Shot，再提交故事板。

**Master Shot 工作流**：
1. 收集参考图：角色图（所有在场角色）+ 场景图，**不传道具图**
2. 生成单张 16:9 全景图——所有在场角色全身可见，空间关系明确
3. 用户确认空间关系和色调满意
4. 压缩为 JPG 控制 payload，存入故事板目录：`storyboards/{故事板名}/master_shot.jpg`
5. meta.json 写入 `master_shot` 字段记录文件名
6. 作为最后一张参考图（Image D/E）传入故事板提交，提示词声明 `Use Image D as the MASTER SPATIAL REFERENCE`

**Master Shot 生成要点**：
- 比例：16:9（单张全景图）
- 色调：与项目一致（都市写实 = `cool grey-blue, muted naturalistic, modern digital cinema, NO film grain`）
- 所有在场角色必须同时出现且全身可见，不能漏人
- 空间关系必须明确（谁在左、谁在右、距离感）

### 标准故事板模板

```
Use Image A as the character reference for [角色A名].
Use Image B as the character reference for [角色B名].（如有）
Use Image C as the environment reference for [场景名].
[如有Master Shot] Use Image D as the MASTER SPATIAL REFERENCE — replicate this exact spatial layout in every panel.

Create a clean 3x3 cinematic storyboard grid in full color.

Image A defines [角色A]: [年龄、体型、发型、服装关键词]
Image B defines [角色B]: [年龄、体型、发型、服装关键词]（如有）
Image C defines the environment: [场景描述]
[如有Master Shot] Image D defines the FIXED SPATIAL LAYOUT — camera angle, character positions, and set dressing must match Image D in every panel exactly.

[多角色场景必须加] FIXED SPATIAL ANCHOR — maintain across ALL panels:
- [元素A]：always [位置描述，如 LEFT side of frame]
- [元素B]：always [位置描述，如 RIGHT side of frame]
- Camera axis: [镜头朝向，如 perpendicular to the alley, stable, does not rotate]
- [角色A] facing direction: [朝向描述]
- [角色B] facing direction: [朝向描述]

[多角色场景必须加] CRITICAL: [角色A] must be visible in every panel. [角色B] must be visible in every panel. Do not omit any character.

NOT a game CG screenshot. NOT a 3D render. NOT anime.
Modern digital cinema camera, live-action feature film production stills.
Color palette: [色调描述，如 cool grey-blue, muted naturalistic / warm indoor lamp light]
NO film grain, NO vintage look unless specified.

Panel sequence:
1. [shot type] — [动作描述，含所有在场角色的位置+朝向]
2. [shot type] — [动作描述，含所有在场角色的位置+朝向]
3. [shot type] — [动作描述，含朝向，如需背对镜头明确写 BACK TO CAMERA]
4. [shot type] — [动作描述]
5. [shot type] — [动作描述]
6. [shot type] — [动作描述]
7. [shot type] — [动作描述]
8. [shot type] — [动作描述]
9. [shot type] — [动作描述]

Style: full-color cinematic storyboard, live-action production still board, realistic perspective, coherent spatial continuity, consistent character faces and costumes across all panels.
No text, no captions, no panel numbers, no watermark.
```

### 每格 panel 描述规则（防止角色消失）

每格动作描述**必须**包含：
1. **shot type**：来自 panels.shot 字段，如 `wide shot`、`medium close-up`
2. **主角动作**：这格的核心动作
3. **所有在场角色的位置**：即使某角色是背景，也要写 `[角色B] visible at [位置]`
4. **身体朝向**（如有朝向歧义）：`BACK TO CAMERA` / `facing LEFT` / `facing camera`

**错误示例**：
```
3. medium shot — 江宁回头挥手  ← 只写了江宁，婉瑜消失；没写朝向，模型默认正对镜头
```

**正确示例**：
```
3. medium shot — 江宁 BACK TO CAMERA facing LEFT toward building entrance, right arm raised waving;
   婉瑜抱着小乐站在画面左侧入口处，面朝镜头方向挥手回应
```

**动作填充逻辑**：用户提供整体描述，拆解为 9 个连续镜头动作，每格写明所有角色位置。展示给用户确认后再提交。

---

## 模板路由总结

```
分类判定 → 模板选择
├── characters        → 模板一：角色设定板
├── scenes_props      → 模板二：场景参考板 / 道具参考板（根据描述内容自动判断）
├── storyboards       → 模板三：故事板（必须有参考图）
└── others            → 无模板，直接使用用户 prompt 或简单扩写
```
