# 4. 容错与恢复机制 (Robustness & Recovery)

## 4.1 异常处理策略

### 4.1.1 异常分类

| 分类 | 描述 | 影响范围 | 处理策略 |
|:---|:---|:---|:---|
| **Fatal Error** | 致命错误 | 整个系统 | 直接阻断，抛出明确错误 |
| **Task Failure** | 任务级失败 | 单个任务 | Early Exit 或重试 |
| **Timeout** | 执行超时 | 单个任务 | 看门狗介入 |
| **API Error** | API 调用错误 | 网络/模型 | 重试或降级 |

### 4.1.2 致命错误 (Fatal Error)

#### 定义

| 错误类型 | 描述 | 处理方式 |
|:---|:---|:---|
| API Key 耗尽 | LLM API 配额用尽 | 阻断，向前端抛出错误码 |
| 网络连接失败 | 无法访问外部服务 | 阻断，提示检查网络 |
| 服务不可用 | Gateway/Agent 服务崩溃 | 阻断，触发告警 |

#### 错误响应格式

```json
{
  "error": {
    "code": "FATAL_API_KEY_EXHAUSTED",
    "message": "API Key 已用尽，请检查配置",
    "severity": "FATAL",
    "recoverable": false
  }
}
```

### 4.1.3 任务级失败 (Task Failure)

#### 定义

| 场景 | 描述 | 处理方式 |
|:---|:---|:---|
| 可行性不通过 | 创新性/原创性不足 | Early Exit |
| 文献检索失败 | 找不到相关文献 | 重试或跳过 |
| 审查未通过 | 逻辑问题/重复率高 | 循环迭代修复 |

#### Early Exit 流程

```
[Task 执行失败]
    ↓
[判断是否为 Early Exit 场景]
    ├── [是: 不可行分析]
    │   → 生成《可行性分析报告》
    │   → 通知用户终止原因
    │   → 清理工作区
    │   → 任务结束
    │
    └── [否: 重试策略]
        → 重试次数 < 最大重试?
            ├── [是] → 尝试修复 → 重新执行
            └── [否] → 终止 → 错误报告
```

---

## 4.2 超时与看门狗机制

### 4.2.1 看门狗设计

为每个 SubAgent 挂载一个 Watchdog（看门狗）：

```
┌─────────────────────────────────────────┐
│           SubAgent                      │
│         (Investigator/                  │
│          Writer/Reviewer)               │
└─────────────────────────────────────────┘
         ↑                       ↑
    ┌────────┐             ┌────────┐
    │ Watchdog │             │ Timer  │
    │ 看门狗  │             │ 计时器 │
    └────────┘             └────────┘
```

### 4.2.2 超时时间线

```
T+0:   任务开始计时
        ↓
T+30s: (可选) 早期提示
        ↓
T+1min: 若无任何有效输出 → Soft Restart
        - 更换 Prompt 策略
        - 或调用降级模型
        ↓
T+2min: (可选) 第二次重试
        ↓
T+3min: 若仍无进展 → Hard Stop
        - 抛出 TimeoutError
        - 回传给 Editor
        - Editor 决定跳过或终止
```

### 4.2.3 超时配置

| 节点 | 建议超时 | Soft Restart | Hard Stop |
|:---|:---:|:---:|:---:|
| Intent Analysis | 30s | 不可用 | 30s |
| Feasibility Study | 2min | 1min | 3min |
| Deep Research | 5min | 2min | 5min |
| Drafting | 3min | 1min | 3min |
| Review | 2min | 1min | 2min |
| Polishing | 2min | 1min | 2min |
| Publishing | 30s | 10s | 30s |

### 4.2.4 Soft Restart 策略

#### 策略1：更换 Prompt 策略

```json
{
  "strategy": "refine_prompt",
  "actions": [
    "简化 Prompt",
    "减少约束条件",
    "聚焦核心要点"
  ]
}
```

#### 策略2：降级模型

```json
{
  "strategy": "model_downgrade",
  "actions": [
    "gpt-4o → gpt-4o-mini",
    "claude-3.5-sonnet → claude-3-haiku"
  ]
}
```

#### 策略3：拆分任务

```json
{
  "strategy": "split_task",
  "actions": [
    "将大任务拆分为小任务",
    "逐个执行",
    "合并结果"
  ]
}
```

#### Soft Restart → 节点映射矩阵

| 节点 | 推荐策略 | 备选策略 | 不适用策略 |
|:---|:---:|:---:|:---:|
| Intent Analysis | (不适用) | (不适用) | 全部 |
| Feasibility Study | refine_prompt | model_downgrade | split_task |
| Deep Research | refine_prompt | split_task | model_downgrade |
| Drafting | model_downgrade | refine_prompt | split_task |
| Review | refine_prompt | split_task | model_downgrade |
| Polishing | model_downgrade | refine_prompt | split_task |
| Publishing | (不适用) | (不适用) | 全部 |

> **注**：Publishing 为轻量操作，通常不使用 Soft Restart。

---

## 4.3 重试与回退策略

### 4.3.1 重试配置

| 错误类型 | 最大重试 | 间隔策略 | 回退策略 |
|:---|:---:|:---:|:---|
| 网络错误 | 3 | 指数回退 | 更换 API |
| 模型错误 | 2 | 固定 | 降级模型 |
| 内容审查 | 1 | 0 | 修改 Prompt |
| 超时 | 2 | 线性 | 拆分任务 |

### 4.3.2 重试间隔公式

```
interval = base * (exponent ^ retryCount)

// 指数回退: 1s, 2s, 4s, 8s...
// 线性回退: 1s, 2s, 3s...
```

#### 4.3.3 重试策略优先级

**重试决策顺序**：

1. **错误类型优先** (04表) — 首先根据错误类型判断重试策略
2. **节点配置覆盖** (01表) — 当特定节点有明确配置时，节点配置优先于错误类型默认配置
3. **降级链路** — 最后手段：模型降级

**优先级示例**：

```
场景: Feasibility Study (节点2) 发生超时

1. 检查 04 表: 超时错误 → 最大重试2次，拆分任务
2. 检查 01 表: 节点2 → 最大重试2次，更换搜索API
3. 优先级: 节点配置(01)优先于错误类型配置(04)
   → 执行: 更换搜索API，最大重试2次

场景: 发生网络错误 (任何节点)

1. 检查 04 表: 网络错误 → 最大重试3次，指数回退
2. 检查节点配置 (如有)
3. 优先级: 错误类型优先 (网络错误需快速响应)
   → 执行: 更换API，最大重试3次
```

> **注**：具体节点重试配置详见 `01_PRD_and_Workflow.md` 第200-208行。

### 4.3.3 降级链路

```
[首选模型: gpt-4o]
    ↓ (失败)
[降级模型: gpt-4o-mini]
    ↓ (失败)
[备选模型: claude-3.5-sonnet]
    ↓ (失败)
[最终降级: gpt-3.5-turbo]
    ↓ (失败)
[终止任务]
```

---

## 4.4 健康检查与告警

### 4.4.1 健康检查端点

| 端点 | 描述 |
|:---|:---|
| `/health` | 系统健康状态 |
| `/health/llm` | LLM 服务状态 |
| `/health/storage` | 存储服务状态 |

### 4.4.2 状态响应

```json
{
  "status": "HEALTHY | DEGRADED | UNHEALTHY",
  "checks": {
    "llm": "UP | DOWN",
    "storage": "UP | DOWN",
    "network": "UP | DOWN"
  },
  "timestamp": "2026-05-03T10:00:00Z"
}
```

### 4.4.3 告警规则

| 级别 | 条件 | 动作 |
|:---:|:---|:---|
| INFO | 任务超时 | 记录日志 |
| WARNING | 连续3次失败 | 通知 Editor |
| ERROR | 服务不可用 | 告警 + 阻断 |
| CRITICAL | API Key 耗尽 | 告警 + 终止 |

---

## 4.5 任务状态管理

### 4.5.1 任务状态机

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│  PENDING │────▶│ RUNNING │────▶│ COMPLETED │
└─────────┘     └─────────┘     └─────────┘
      ▲            │            │
      │            ▼            ▼
      │       ┌─────────┐     ┌─────────┐
      └──────│ FAILED │     │ CANCELLED│
             └─────────┘     └─────────┘
```

### 4.5.2 状态定义

| 状态 | 描述 | 是否终态 |
|:---|:---|:---:|
| PENDING | 等待执行 | ❌ |
| RUNNING | 执行中 | ❌ |
| PAUSED | 已暂停（可恢复） | ❌ |
| COMPLETED | 执行完成 | ✅ |
| FAILED | 执行失败 | ✅ |
| CANCELLED | 已取消 | ✅ |

> **注**：PAUSED 状态用于支持"中断后恢复"（Pause & Resume）。用户可主动暂停任务，后续通过 Resume API 恢复执行。

### 4.5.3 任务元数据

```json
{
  "taskId": "task_001",
  "type": "research",
  "status": "RUNNING",
  "createdAt": "2026-05-03T10:00:00Z",
  "startedAt": "2026-05-03T10:00:01Z",
  "updatedAt": "2026-05-03T10:02:00Z",
  "currentNode": "deepResearch",
  "retryCount": 0,
  "errorCount": 0,
  "subTasks": [
    {"id": "sub_001", "status": "COMPLETED"},
    {"id": "sub_002", "status": "RUNNING"},
    {"id": "sub_003", "status": "PENDING"}
  ]
}
```

---

## 4.6 日志与追踪

### 4.6.1 日志级别

| 级别 | 描述 | 使用场景 |
|:---:|:---|:---|
| DEBUG | 调试信息 | 开发调试 |
| INFO | 一般信息 | 正常流程 |
| WARNING | 警告 | 可恢复的错误 |
| ERROR | 错误 | 执行失败 |
| CRITICAL | 致命错误 | 系统崩溃 |

### 4.6.2 日志格式

```
[2026-05-03T10:00:00.123Z] [INFO] [Editor] Task-001: 任务开始执行
[2026-05-03T10:00:01.234Z] [INFO] [Editor] Task-001: 委派给 Investigator
[2026-05-03T10:00:05.567Z] [INFO] [Investigator] Task-001: 执行可行性分析
[2026-05-03T10:01:30.890Z] [WARNING] [Investigator] Task-001: 搜索超时，重试中
[2026-05-03T10:02:00.123Z] [ERROR] [Investigator] Task-001: 执行失败 - 重试次数用尽
```

### 4.6.3 追踪上下文

```json
{
  "traceId": "trace_abc123",
  "spanId": "span_001",
  "parentSpanId": null,
  "taskId": "task_001",
  "node": "deepResearch",
  "agent": "Investigator"
}
```

---

## 4.7 恢复检查点

### 4.7.1 Checkpoint 设计

在关键节点保存恢复点：

| 节点 | Checkpoint | 恢复方式 |
|:---|:---:|:---|
| 1. Intent Analysis | ✅ | 从头重跑 |
| 2. Feasibility | ✅ | 从头重跑 |
| 3. Deep Research | ✅ | 跳过，从缓存读 |
| 4. Drafting | ✅ | 跳过，从缓存读 |
| 5-6. Review | ❌ | 不支持恢复 |
| 7. Polishing | ❌ | 不支持恢复 |
| 8. Publishing | ✅ | 重新生成 |

### 4.7.2 缓存策略

```
[Checkpoint 存储]
    ↓
[共享区]
    ├── investigation_results/
    ├── writer_drafts/
    └── checkpoint.json
    ↓
[恢复时]
    → 检查缓存是否存在
    → 询问用户是否使用缓存
    → 或从头重跑
```

### 4.7.3 Pause & Resume (中断后恢复)

支持用户主动暂停任务并后续恢复执行。

#### 状态转换

```
RUNNING → PAUSED → RUNNING (恢复)
PAUSED → COMPLETED (用户确认继续)
PAUSED → CANCELLED (用户取消)
```

#### API 定义

| 端点 | 方法 | 描述 |
|:---|:---:|:---|
| `/api/research/{taskId}/pause` | POST | 暂停任务 |
| `/api/research/{taskId}/resume` | POST | 恢复任务 |
| `/api/research/{taskId}/status` | GET | 查询任务状态 |

#### 暂停时的数据持久化

当任务进入 PAUSED 状态时：

```json
{
  "taskId": "task_001",
  "status": "PAUSED",
  "pausedAt": "2026-05-03T10:30:00Z",
  "checkpoint": {
    "node": "drafting",
    "subTaskId": "sub_002",
    "sharedContextSnapshot": "investigation_results/draft_v1.md"
  },
  "resumeToken": "resume_abc123"  // 用于恢复的唯一令牌
}
```

#### 恢复时的行为

1. 验证 `resumeToken` 有效性
2. 加载 `sharedContextSnapshot` 到共享区
3. 从 `subTaskId` 继续执行
4. 清除 `resumeToken`（防止重复恢复）

#### 注意事项

- 暂停仅在节点执行完成后触发（不能中断原子操作）
- 长时间暂停后恢复可能面临上下文过期，需用户重新确认
- 建议最大暂停时长：24小时（超时自动终止）

---

## 4.8 优雅终止

### 4.8.1 终止信号处理

```json
{
  "signals": [
    "SIGINT (Ctrl+C)",
    "SIGTERM (Kill)",
    "SIGQUIT (Quit)"
  ],
  "actions": [
    "1. 保存当前进度到 Checkpoint",
    "2. 取消正在执行的任务",
    "3. 清理临时文件",
    "4. 关闭连接",
    "5. 通知前端终止"
  ]
}
```

### 4.8.2 强制终止条件

| 条件 | 超时时间 | 动作 |
|:---|:---:|:---|
| 任务卡死 | 10min | 强制终止 |
| 内存泄漏 | - | 强制终止 |
| 死循环 | - | 强制终止 |

---

## 4.9 错误代码表

| 错误代码 | 描述 | 严重级 | 可恢复 |
|:---|:---|:---:|:---:|
| ERR_INIT_001 | 系统初始化失败 | CRITICAL | ❌ |
| ERR_LLM_001 | API Key 无效 | CRITICAL | ❌ |
| ERR_LLM_002 | API Key 耗尽 | CRITICAL | ❌ |
| ERR_NET_001 | 网络不可达 | ERROR | ✅ |
| ERR_NET_002 | 请求超时 | ERROR | ✅ |
| ERR_TASK_001 | 任务超时 | WARNING | ✅ |
| ERR_TASK_002 | 任务失败 | WARNING | ✅ |
| ERR_VALIDATE_001 | 逻辑校验失败 | INFO | ✅ |
| ERR_VALIDATE_002 | 重复率超标 | INFO | ✅ |
| ERR_PERM_001 | 权限不足 | ERROR | ❌ |

---

*Last Updated: 2026-05-03*