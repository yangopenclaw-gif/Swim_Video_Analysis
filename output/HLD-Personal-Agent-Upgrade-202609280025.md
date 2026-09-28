# 个人专属智能体升级 —— 顶层架构设计（HLD）

## 1. Document Information

| 项 | 内容 |
|------|------|
| 文档类型 | HLD（High-Level Design，高层架构设计） |
| 主题 | 将「个人记账本」升级为「个人专属智能体」 |
| 版本 | v1.0（待审核） |
| 作者 | AI Agent |
| 日期 | 2026-09-28 |
| 状态 | 待审核（审核通过后进入 LLD 与编码） |
| 受众 | 架构 / 开发 / 决策 |

---

## 2. Background and Objectives

### 2.1 背景与现状

当前产品是一个移动端「个人记账本」（Android 原生，Kotlin + Jetpack Compose），后端为 FastAPI + SQLite。已具备：账单记录、月度/分类统计、语音记账（parse_voice 单次识别）、密码 + 指纹双重安全、从后台恢复自动锁屏。

仓库历史包袱：由「游泳视频分析平台」演变而来，保留大量游泳分析遗留死代码（47 个游泳端点、v4 算法模块、Web 前端、模型资产），记账本实际仅依赖约 12 个后端端点。

### 2.2 目标

1. 将应用升级为**个人专属智能体（Personal AI Agent）**，而非单一记账工具。
2. **复用现有客户端与后端代码**，逐步演进、持续做强，不做推倒重来。
3. 客户端新增**语音交互界面**（对话式，语音输入 + 流式回复 + 语音播报）。
4. 后端构建**智能体架构**：大模型编排 + 工具调用 + 记忆持久化 + 知识库。
5. 接入 **DeepSeek** 大模型。
6. 现有记账本功能**作为智能体的一个子功能（工具）继续保留**。
7. 一期落地 3 个日常场景（用户勾选）：**语音记账 + 智能理财分析、日程提醒/备忘、个人知识问答**。

### 2.3 设计原则

- **最高性价比**：轻量自研、单机可跑、按 token 精打细算、优先复用现有能力。
- **业界最佳实践**：ReAct 编排、Function Calling、分层记忆、RAG、MCP 扩展标准。
- **渐进演进**：先单 Agent + 工具，后续可平滑升级到多 Agent / 更复杂编排。
- **复用优先**：记账本数据、认证、安全机制全部保留并作为工具暴露给智能体。

### 2.4 一期范围界定（建议，待审核）

三个场景按「性价比 / 见效速度」建议分三步，一期聚焦第一个，其余作为紧随其后的二期/三期：

| 期次 | 场景 | 理由 |
|------|------|------|
| 一期（本次核心） | 语音记账 + 智能理财分析 | 复用现有 ledger 数据与接口，成本最低、最快见效、最能验证 Agent 架构 |
| 一期底座 | 记忆持久化（短期 + 长期） | 智能体的核心差异化能力，须与一期同步搭建 |
| 二期 | 日程提醒 / 备忘 | 新数据表 + 定时任务，中等成本 |
| 三期 | 个人知识问答（RAG 知识库） | 需完整 RAG 管道，成本最高、价值最大 |

> 说明：用户勾选了三个场景，本设计均覆盖；但建议分阶段交付以控制风险、快速拿到可用成果。

---

## 3. System Architecture Diagram

整体采用「客户端 / Agent 服务层 / 能力层 / 模型层 / 数据层」的分层架构。一期保持单机单体部署，逻辑上分层、物理上可拆分。

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端（Android）                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────┐ ┌────────────┐ │
│  │ 语音交互界面 │ │  账单(子功能)│ │  统计    │ │ 我的/安全   │ │
│  │ ChatScreen  │ │  Ledger UI  │ │ Stats   │ │ Profile    │ │
│  └──────┬──────┘ └─────────────┘ └─────────┘ └────────────┘ │
│         │ ASR(语音→文本) / TTS(文本→语音) / SSE(流式接收)      │
└─────────┼───────────────────────────────────────────────────┘
          │ HTTPS (JWT)
┌─────────▼───────────────────────────────────────────────────┐
│                后端 Agent 服务层（FastAPI 扩展）               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Agent Core（ReAct 编排循环）             │   │
│  │   规划(LLM) → 工具调用(Function Call) → 观察 → 答复    │   │
│  └──────┬───────────────┬───────────────┬───────────────┘   │
│         │               │               │                   │
│  ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐            │
│  │ LLM Gateway │ │ Tool Registry│ │ Memory Srv │            │
│  │ (DeepSeek)  │ │ (工具注册表) │ │ (分层记忆) │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│         │               │               │                   │
│  ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐            │
│  │Knowledge Srv│ │Schedule Srv │ │ Ledger Srv  │            │
│  │ (RAG 知识库)│ │ (日程提醒)  │ │(记账本,保留)│            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────┬───────────────┬───────────────┬───────────────────┘
          │               │               │
┌─────────▼──────┐ ┌──────▼──────┐ ┌──────▼───────────────────┐
│   模型层       │ │   向量库     │ │   数据层（SQLite）        │
│ DeepSeek API   │ │ Qdrant/sqlite│ │ users/ledger/            │
│ Embedding API  │ │ -vec        │ │ conversations/memories/  │
│ (硅基流动/自托管)│ │             │ │ documents/schedules      │
└────────────────┘ └─────────────┘ └──────────────────────────┘
```

---

## 4. Module / Service Decomposition

### 4.1 客户端模块（Android）

| 模块 | 说明 | 状态 |
|------|------|------|
| ChatScreen（语音交互界面） | 对话式气泡 UI，底部麦克风，语音输入 + SSE 流式渲染 + TTS 播报 | **新增** |
| Ledger / Stats / AddEntry | 现有记账本页面 | 保留，作为子功能 |
| Profile（我的） | 保留，新增「清除记忆 / 知识库管理」入口 | 增强 |
| ASR / TTS 封装 | 封装系统 SpeechRecognizer / TextToSpeech，可切换云端 ASR | **新增** |
| AgentApi（SSE 客户端） | 新增 `chat` 流式接口调用 | **新增** |

导航调整：底部导航由「统计 / 账单 / 我的」扩展为「**助手（默认页）** / 统计 / 账单 / 我的」四页签，语音交互界面作为启动默认页。

### 4.2 后端模块（FastAPI）

| 模块 | 职责 | 状态 |
|------|------|------|
| Agent Core | ReAct 编排：组装系统提示 + 记忆 + 工具列表 → 调 LLM → 解析工具调用 → 执行 → 回填 → 直至产出答复 | **新增** |
| LLM Gateway | 统一封装 DeepSeek（deepseek-chat / deepseek-reasoner），流式 SSE、重试、token 预算、模型降级 | **新增** |
| Tool Registry | 声明式注册工具（name/desc/JSON schema + 处理函数），供 Agent 与 MCP 使用 | **新增** |
| Memory Service | 短期会话 + 长期记忆（语义/情景/偏好）读写与摘要压缩 | **新增** |
| Knowledge Service | 文档解析 → 切分 → Embedding → 入库 → 检索 → 重排 | **新增**（三期重点） |
| Schedule Service | 日程 CRUD + 定时提醒（推送/通知） | **新增**（二期） |
| Ledger Service | 现有记账本逻辑，包装为工具（记账/查账/统计） | 保留 + 包装 |
| Auth / Security | 现有 JWT + 密码/指纹 | 保留 |

---

## 5. Core Technology Selection and Rationale

### 5.1 大模型：DeepSeek

| 项 | 选择 | 理由 |
|------|------|------|
| 主模型 | `deepseek-chat`（DeepSeek-V3） | 通用对话 + Function Calling，成本极低，满足记账意图识别与日常对话 |
| 推理模型 | `deepseek-reasoner`（DeepSeek-R1） | 用于复杂理财分析 / 多步推理，按需调用 |
| 调用方式 | OpenAI 兼容 API + Function Calling | 生态成熟、切换成本低 |
| 流式 | SSE | 实现打字机效果，首字延迟更低、体验更好 |

### 5.2 Agent 编排：自研轻量 ReAct + Function Calling（推荐）

| 候选 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 自研 ReAct + Function Calling | 轻量、可控、贴合 DeepSeek、单机友好、无重依赖 | 需自行维护循环逻辑 | ✅ 一期推荐 |
| LangChain | 组件丰富、抽象全 | 重、抽象多、版本迭代快、学习/维护成本高 | 二期按需引入 |
| LlamaIndex | RAG/数据框架强 | 偏数据侧，编排弱 | 三期 RAG 可参考 |

一期用自研 ReAct 循环（约几百行），保留「工具注册表」为标准接口，后续可平滑演进到多 Agent、甚至以 **MCP（Model Context Protocol）** 标准暴露工具与知识库，让智能体能接入更多外部数据源。

### 5.3 记忆持久化：分层记忆（参考 MemGPT/Letta 思想）

| 层 | 内容 | 存储 | 说明 |
|------|------|------|------|
| 短期记忆 | 当前会话消息（rolling window + 自动摘要压缩） | SQLite conversations / messages | 控制 token 预算 |
| 长期记忆-语义 | 用户偏好、事实（如「我喜欢用微信支付」「每周五游泳」） | SQLite memories + embedding 列 | 语义检索召回 |
| 长期记忆-情景 | 重要事件（如「上个月换了新手机」） | SQLite memories（type=event） | 按时间/相关性召回 |
| 记忆工具化 | `memory_save` / `memory_recall` 两个工具 | — | 让 LLM 自主读写，而非硬编码 |

记忆写入策略：对话结束后由 LLM 抽取值得长期记住的偏好/事实/事件，异步写入；检索时按相关性 + 时效召回注入上下文。

### 5.4 知识库（RAG）

| 环节 | 选择 | 理由 |
|------|------|------|
| 文档解析 | pypdf / python-docx / markdown / txt | 覆盖常见个人文档 |
| 文本切分 | 语义切分 + 固定窗口兜底（中文友好） | 提升检索质量 |
| Embedding | 硅基流动 `BAAI/bge-m3` API（或自托管 bge-large-zh-v1.5） | DeepSeek 暂无 Embedding，需第三方；中文效果好、性价比高 |
| 向量库 | 单机：Qdrant 嵌入式 或 sqlite-vec | 与现有单机部署一致；sqlite-vec 可与 SQLite 统一、最轻量 |
| 检索 | 向量召回 Top-K + 关键词 BM25 混合 | 提升召回 |
| 重排序 | bge-reranker（可选，二期） | 提升精排 |

### 5.5 语音：ASR / TTS

| 环节 | 一期选择 | 升级选项 |
|------|------|------|
| ASR（语音→文本） | Android 系统 SpeechRecognizer（免费，已有语音记账基础） | 阿里云 NLS / 讯飞 / 火山 / Whisper（中文更好） |
| TTS（文本→语音） | Android 系统 TextToSpeech（免费） | Edge-TTS（免费微软音色）/ 阿里云 / MiniMax |

一期复用系统能力，零成本；后续按语音质量需求平滑切换云端服务。

### 5.6 数据存储

| 数据 | 一期 | 说明 |
|------|------|------|
| 关系数据 | SQLite（沿用） | users / ledger_entries / conversations / messages / memories / schedules / documents |
| 向量数据 | sqlite-vec 或 Qdrant 嵌入式 | 记忆召回 + 知识库检索 |

---

## 6. Data Flow / Call Chain Description

### 6.1 语音记账（一期核心链路）

1. 用户对 ChatScreen 说「帮我记一笔，午饭花了 30 块」。
2. 客户端 ASR 转文本 → 携带 JWT 调用 `POST /api/agent/chat`（SSE）。
3. Agent Core 组装上下文：系统提示 + 长期记忆召回 + 工具列表（含 `ledger_add`）。
4. LLM 判断意图，返回 `ledger_add` 工具调用（参数：type=expense, amount=30, category=餐饮, note=午饭）。
5. Tool Registry 执行 `ledger_add` → 调用 Ledger Service 写入 `ledger_entries`。
6. 执行结果回填 → LLM 生成自然语言答复「已帮你记好：午饭 30 元，记入餐饮分类」。
7. 通过 SSE 流式返回文本 → 客户端渲染 + TTS 播报。
8. 会话结束后异步抽取记忆（如「用户常在午餐时间记账」）写入长期记忆。

### 6.2 智能理财分析

1. 用户说「这个月我花多了吗，分析一下」。
2. Agent 调用 `ledger_summary` / `ledger_query` 工具获取统计与明细。
3. 必要时切换 `deepseek-reasoner` 做推理分析，给出分类占比、趋势、省钱建议。

### 6.3 知识问答（三期）

1. 用户说「我上周存的体检报告里血糖是多少」。
2. Agent 调用 `kb_search` 工具 → Knowledge Service 向量检索 Top-K 片段 → 重排 → 返回给 LLM 生成答案。

### 6.4 记忆读写

1. 对话中/结束时，LLM 主动调用 `memory_save` 保存偏好/事实/事件。
2. 每轮对话开始，Memory Service 按相关性 + 时效召回长期记忆注入上下文，实现「越用越懂你」。

---

## 7. Key Interface Definitions (High-Level)

### 7.1 核心接口：流式对话

    POST /api/agent/chat
    Headers: Authorization: Bearer <jwt>
    Body: { "conversation_id": "uuid", "message": "帮我记一笔午饭30块" }
    Response: text/event-stream (SSE)
      event: delta
      data: {"text":"已"}
      ...
      event: done
      data: {"conversation_id":"uuid","tool_calls":[...]}

### 7.2 工具注册表（Function Calling 语义）

每个工具统一为 `{ name, description, parameters(JSON Schema), handler }`，一期工具集：

| 工具 | 说明 |
|------|------|
| ledger_add | 记一笔（支出/收入、金额、分类、备注、日期、币种） |
| ledger_query | 按年月/分类查账 |
| ledger_summary | 统计（支出/收入/分类占比） |
| schedule_add / schedule_list | 日程（二期） |
| kb_search | 知识库检索（三期） |
| memory_save / memory_recall | 记忆读写 |

### 7.3 数据模型（新增表，高层面）

| 表 | 关键字段 | 说明 |
|------|------|------|
| conversations | id, user_id, title, created_at | 会话 |
| messages | id, conversation_id, role, content, tool_calls, created_at | 消息（含工具调用） |
| memories | id, user_id, type(profile/event/preference), content, embedding, importance, created_at | 长期记忆 |
| schedules | id, user_id, title, remind_at, status | 日程 |
| documents / chunks | id, user_id, source, content, embedding | 知识库（三期） |

### 7.4 客户端数据模型（新增）

| 类 | 说明 |
|------|------|
| ChatMessage | role(user/assistant), text, isStreaming |
| AgentApi | 调用 `/api/agent/chat`，OkHttp SSE 解析流式 delta |

---

## 8. Non-Functional Design

### 8.1 性能

- 流式首字延迟目标：< 2s（DeepSeek 流式 + SSE）。
- token 预算控制：短期记忆滚动窗口 + 超长对话自动摘要压缩，避免上下文爆炸。
- 向量检索：单机百万级以内，sqlite-vec / Qdrant 足够。

### 8.2 安全与隐私（个人专属智能体的核心）

- 延续现有 JWT + 密码 + 指纹；智能体涉及个人财务/记忆/知识库，敏感数据不出个人后端。
- Embedding 若走第三方 API，仅上传切分后的文本片段，脱敏可选。
- 密钥（DeepSeek/Embedding API Key）通过环境变量管理，不入库、不入仓库。

### 8.3 成本（最高性价比关键）

- 主用 `deepseek-chat`（极低成本），推理/分析按需 `deepseek-reasoner`。
- ASR/TTS 一期复用系统能力，零额外成本。
- 长期记忆 embedding 仅对「值得记住」的内容入库，控制向量规模。
- 上下文缓存 / 摘要压缩降低重复 token 消耗。

### 8.4 可用性与降级

- LLM 失败 → 降级为规则式意图识别（关键词匹配记账），保证核心记账可用。
- 工具执行失败 → 明确向用户反馈，不静默吞错。
- 语音失败 → 回退为文字输入。

---

## 9. Deployment Architecture

一期保持**单机单体**部署（与现状一致），逻辑分层、物理单进程，降低运维成本：

    ┌───────────────────────────────────────────┐
    │  云服务器（139.159.249.62，单机）            │
    │  FastAPI（含 Agent Core + 各 Service）      │
    │  SQLite（关系数据）+ sqlite-vec/Qdrant(向量) │
    │  环境变量：DEEPSEEK_API_KEY 等               │
    └──────────────┬────────────────────────────┘
                   │ 出网 HTTPS
    ┌──────────────▼────────────────────────────┐
    │  DeepSeek API / Embedding API（云）        │
    └───────────────────────────────────────────┘

- 构建/发布：沿用现有 GitHub Actions（push master 自动编译 Android APK + Release）。
- 后端：沿用 `uvicorn` 启动，新增依赖在 `requirements.txt` 增补（需补齐当前缺失的 sqlalchemy/python-dotenv/bcrypt/PyJWT/httpx）。
- 演进方向：向量库独立进程、Agent 服务独立、Redis 缓存、对象存储，按需逐步拆出。

---

## 10. Risks and Open Decisions

### 10.1 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| ASR 中文识别不准（系统引擎） | 记账参数错误 | 先做「识别→确认」回显，必要升级云端 ASR |
| LLM 幻觉导致错误记账 | 财务数据错误 | 工具参数强校验 + 关键操作需用户确认 |
| 个人数据隐私 | 敏感信息泄露 | 本地后端 + 密钥管理 + 最小化上传 |
| 单点故障（单机） | 服务不可用 | 一期接受，后续冗余 |

### 10.2 待确认（Open Decisions）

- [TBD: 一期是否严格只做「语音记账+理财分析」，日程/知识问答是否确认为二期/三期]
- [TBD: 是否有预算使用云端 ASR/TTS（阿里/讯飞/火山），还是一期纯系统能力]
- [TBD: Embedding 是否可接受第三方 API（硅基流动），还是必须自托管]
- [TBD: 语音交互界面的视觉风格是否延续「珊瑚橙→蜜桃 + 可爱」方向]
- [TBD: 是否清理游泳分析遗留死代码，以降低仓库复杂度]

---

## 附：分期路线（Milestones）

| 阶段 | 交付物 | 说明 |
|------|------|------|
| Phase 0 | Agent 内核 + LLM Gateway + 工具注册表 + 语音交互界面 + 语音记账/查账/统计/理财分析 + 记忆底座 | 本期核心，复用 ledger，最快见效 |
| Phase 1 | 日程提醒/备忘（Schedule Service + 通知） | 二期 |
| Phase 2 | 知识库 RAG（文档解析/Embedding/检索/问答） | 三期 |
| Phase 3 | MCP 标准化、多 Agent、多数据源接入 | 演进 |