# 2. 系统架构 (System Architecture)

## 2.1 整体分层架构

系统采用分层架构设计，从前端到后端依次为：客户端层、网关层、智能体框架层。

```
┌─────────────────────────────────────────┐
│           Layer 1: Frontend            │
│           (Client / User UI)           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│           Layer 2: Gateway             │
│      (BFF & Security & Router)         │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      Layer 3: Agentic Framework        │
│   (Editor + Workers Orchestration)      │
└─────────────────────────────────────────┘
```

---

## 2.2 Layer 1: Frontend (客户端)

### 职责

| 功能 | 描述 |
|:---|---|
| 用户输入 | 接收研究主题、学科领域、文档类型等信息 |
| 任务状态显示 | 通过 SSE 流式显示任务进度 |
| 文档下载 | 提供最终文档的下载服务 |

### 技术要求

- 支持 WebSocket 或 SSE 进行实时状态推送
- 支持 Markdown/PDF 预览和下载
- 响应式设计，支持移动端访问

---

## 2.3 Layer 2: Gateway (网关)

### 2.3.1 路由分发 (Router)

网关负责根据请求类型分发到不同的处理路径：

| 路由 | 路径 | 描述 |
|:---:|:---:|---|
| `/api/chat` |闲聊路由 | 直接与 LLM 交互，用于问答 |
| `/api/research` |研究任务路由 | 触发完整的工作流 |

#### 路由判定规则

```
IF (请求包含 "研究"、"调研"、"写论文"、"写专利") 
    → /api/research
ELSE 
    → /api/chat
```

### 2.3.2 安全守护 (Security Guard)

| 防护类型 | 描述 |
|:---|---|
| Prompt 注入检测 | 识别并拦截 Jailbreak 攻击 |
| 敏感词过滤 | 过滤政治、色情、暴力等敏感内容 |
| 输入验证 | 验证必填字段、格式校验 |

#### 注入检测规则

```json
{
  "forbiddenPatterns": [
    "ignore previous instructions",
    "disregard system prompt",
    "你现在是一个",
    "act as"
  ],
  "action": "BLOCK + ALERT"
}
```

### 2.3.3 LLM 代理 (LLM Proxy)

统一适配不同的 LLM 提供商：

| 提供商 | 支持状态 | 配置方式 |
|:---:|:---:|---|
| OpenAI | ✅ 完全支持 | API Key |
| Anthropic | ✅ 完全支持 | API Key |
| Azure OpenAI | ✅ 兼容支持 | Endpoint + Key |
| Ollama | ✅ 本地支持 | Local Endpoint |

#### 接口统一格式

```json
{
  "provider": "openai | anthropic | azure | ollama",
  "model": "gpt-4o | claude-3-5-sonnet | ...",
  "temperature": 0.0-1.0,
  "maxTokens": 4096
}
```

---

## 2.4 Layer 3: Agentic Framework (智能体框架)

### 2.4.1 Editor + Workers 架构

采用 Supervisor-Worker 层级架构：

```
┌─────────────────────────────────────────┐
│           Editor (Supervisor)          │
│         主控与最终打磨者                │
└────────��────────────────────────────────┘
         ↑          ↑          ↑
    ┌────────┐ ┌────────┐ ┌────────┐
    │Investi-│ │ Writer │ │Reviewer│
    │ gator  │ │        │ │        │
    └────────┘ └────────┘ └────────┘
```

### 2.4.2 智能体配置

| 智能体 | 模型建议 | 职责 |
|:---:|:---:|---|
| Editor | GPT-4o / Claude-3.5-Sonnet | 任务编排、上下文管理、最终润色 |
| Investigator | GPT-4o / Claude-3.5-Sonnet | 调研、可行性分析 |
| Writer | GPT-4o / Claude-3.5-Sonnet | 文档起草 |
| Reviewer | GPT-4o / Claude-3.5-Sonnet | 逻辑校验、查重 |

---

## 2.5 Context 与数据流转 (Strict Routing)

### 2.5.1 上下文隔离规则

为防止上下文污染和 Token 浪费，设定严格的 Context 隔离规则：

| 源智能体 | 目标智能体 | 传递内容 |
|:---:|:---:|---|
| Editor | Investigator | 精简版 Task Payload（去除冗余上下文） |
| Editor | Writer | Task + Investigator 产物（共享区读取） |
| Editor | Reviewer | Task + Investigator 产物 + Writer 产物 |
| Investigator | Writer | 产物通过共享区传递，不直接传递 |
| Reviewer | Writer | 评审意见（修改建议） |

### 2.5.2 共享区设计

```
┌─────────────────────────────────────────┐
│            Shared Context              │
│            (共享上下文区)               │
├─────────────────────────────────────────┤
│  investigation_results/                 │
│      - feasibility.json                │
│      - literature_review.md             │
│  writer_drafts/                        │
│      - draft_v1.md                     │
│      - draft_v2.md                     │
│  reviewer_feedback/                     │
│      - review_v1.json                  │
│      - review_v2.json                  │
└─────────────────────────────────────────┘
```

### 2.5.3 Context 生命周期

| 阶段 | Context 内容 | 保留策略 |
|:---:|---|---|
| 任务开始 | 用户输入 + 系统提示 | 保留 |
| 节点2完成 | Feasibility Object | 存入共享区 |
| 节点3完成 | Literature Review | 存入共享区 |
| 节点4完成 | Draft v1 | 存入共享区 |
| 节点5-6完成 | Review Object | 存入共享区 |
| 节点7完成 | Final Draft | 存入共享区 |
| 任务结束 | 所有 Context | **清除**（清理工作区） |

---

## 2.6 内存管理 (Memory Subsystem)

### 2.6.1 短时记忆 (Short-term)

- **定义**：单次任务级的上下文
- **存储位置**：内存 / Redis
- **生命周期**：任务结束后立即释放
- **规则**：**禁止污染其他任务**

### 2.6.2 长时记忆 (Long-term)

- **定义**：工作方法论和通用知识
- **存储位置**：向量数据库 / 文件系统
- **记忆内容**：
  - 学科专业术语库
  - 有效的搜索 Query 技巧
  - 去 AI 化的 Prompt 模板
- **规则**：**不记忆具体业务数据**

### 2.6.3 记忆检索策略

```json
{
  "retrieval": {
    "type": "semantic",
    "topK": 5,
    "threshold": 0.7
  },
  "update": {
    "frequency": "task_end",
    "strategy": "append_only"
  }
}
```

### 2.6.4 未来扩展：MessageBus 消息总线 (Phase 2)

> **状态**：可选扩展，当前版本不需要实现。

**设计背景**：当前采用 Editor-orchestrated 中心化模型，适合 8 步线性工作流。若未来需要支持多任务并行、动态智能体 spawn，可引入 MessageBus。

**候选架构**：

```
┌─────────────────────────────────────────┐
│            MessageBus                   │
│         (消息总线单例)                    │
├─────────────────────────────────────────┤
│  pub/sub 模型                            │
│  - 发布者：Agent                         │
│  - 订阅者：Agent (按 permissions 过滤)    │
│  - 消息格式：带权限标签                   │
└─────────────────────────────────────────┘
```

**消息格式**：

```json
{
  "messageId": "msg_001",
  "from": "Investigator",
  "to": "MessageBus",
  "type": "PUBLISH",
  "payload": {...},
  "permissions": ["writer", "reviewer"],  // 权限标签
  "timestamp": "2026-05-03T10:00:00Z"
}
```

**与当前设计的兼容性**：
- 当前 "Strict Routing" 设计已满足需求
- MessageBus 作为未来扩展，不影响现有架构
-  Phase 1 保持 Editor-orchestrated 模型不变

---

## 2.7 数据流图

```
用户输入
    ↓
[Gateway: 路由判定] → 闲聊? → LLM
    ↓ (研究任务)
[Gateway: 安全检查] → 通过?
    ↓ (通过)
[Editor: Intent Analysis] → {domain, docType}
    ↓
[Editor: 委派 Task to Investigator]
    ↓
[Investigator: Feasibility + Research] → 共享区
    ↓
[Editor: 委派 Task to Writer]
    ↓
[Writer: Drafting] → 共享区
    ↓
[Editor: 委派 Task to Reviewer]
    ↓
[Reviewer: Validation + Check] → 共享区
    ↓ (循环迭代)
[Editor: 委派 Polishing to self]
    ↓
[Editor: Publishing] → 前端通知 + 文件清理
    ↓
任务完成
```

---

## 2.8 配置管理

### 2.8.1 配置文件结构

```yaml
# config/system.yaml
system:
  name: "AutoResearch Agent"
  version: "1.0.0"
  
gateway:
  routes:
    chat: "/api/chat"
    research: "/api/research"
  security:
    forbiddenPatterns:
      - "ignore previous"
      - "disregard system"
    sensitiveWords:
      - "xxx" # 可配置
      
llm:
  providers:
    - name: "openai"
      model: "gpt-4o"
      apiKey: "${OPENAI_API_KEY}"
    - name: "anthropic"
      model: "claude-3-5-sonnet"
      apiKey: "${ANTHROPIC_API_KEY}"
  defaultProvider: "openai"
  
agents:
  editor:
    model: "gpt-4o"
    maxTokens: 4096
  investigator:
    model: "gpt-4o"
    maxTokens: 4096
  writer:
    model: "gpt-4o"
    maxTokens: 4096
  reviewer:
    model: "gpt-4o"
    maxTokens: 4096
    
timeout:
  intentAnalysis: 30
  feasibility: 120
  deepResearch: 300
  drafting: 180
  review: 120
  polishing: 120
  publishing: 30
  
workspace:
  tempDir: "./workspace/temp"
  outputDir: "./workspace/output"
  cleanupPatterns:
    - "*.py"
    - "*.mjs"
    - "*.js"
    - "*.ts"
```

---

*Last Updated: 2026-05-03*