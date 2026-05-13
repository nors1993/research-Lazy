# 1. 业务需求与核心工作流 (PRD & Workflow)

## 1.1 项目愿景

构建一个由多智能体协作的自动化研究与写作系统，实现从用户意图识别、可行性分析、深度调研、论文起草、逻辑校验到最终去AI化润色输出的全链路闭环。

> **设计目标**：让用户只需提供研究主题和期望的文档类型，系统即可自动化完成从调研到发布的完整流程。

---

## 1.2 核心业务工作流 (Workflow DAG)

系统采用有向无环图 (DAG) 或状态机来管理工作流。

### 工作流节点定义

| 序号 | 节点 | 英文名 | 描述 |
|:---:|---|---|---|
| 1 | 意图分析 | Intent Analysis | 提取[学科领域]与[文档类型]（论文/专利/摘要/报告等） |
| 2 | 可行性分析 | Feasibility Study | 评估创新性与原创性。若不可行则触发**Early Exit** |
| 3 | 深度调研 | Deep Research | 基于学科进行文献检索，输出《文献综述与资源列表》 |
| 4 | 大纲与起草 | Drafting | 结合用户模板与调研结果输出《初稿文档》 |
| 5 | 逻辑自洽 | Logic Validation | 审查初稿，确保证明逻辑与推演无误 |
| 6 | 查重控制 | Plagiarism Check | 检索比对，确保重复率 `< 15%` |
| 7 | 润色与去AI化 | Polishing & Humanizing | 抹除大模型常用套话，采用领域专家口吻重写 |
| 8 | 发布与清理 | Publishing | 生成最终排版文档，通知用户保存路径，并**强制执行工作区清理** |

> **注**：节点5和6合并为 Review 阶段，需循环迭代直至通过。

#### Review 循环退出条件

| Review 状态 | 循环动作 |
|:---|:---|
| APPROVED | 进入下一阶段 |
| REJECTED | 终止任务，标记 FAILED |
| MAJOR_REVISION | 循环迭代（最多3次） |
| MINOR_REVISION | 可选择迭代或继续 |

> **注**：Review 状态定义详见 `03_Multi_Agent_Topology.md` 第547行。

### 工作流状态机

```
[用户输入]
    ↓
[1. Intent Analysis] → {学科领域, 文档类型}
    ↓
[2. Feasibility Study] → {可行/不可行}
    ↓ (若可行)
[3. Deep Research] → 文献综述
    ↓
[4. Drafting] → 初稿文档
    ↓
[5-6. Review] ←→ (循环迭代)
    ↓ (通过)
[7. Polishing] → 终稿
    ↓
[8. Publishing] → 交付 + 清理
    ↓
[任务完成]
```

### 工作流状态值

| 状态 | 描述 | 是否终态 |
|:---|:---|:---:|
| PENDING | 等待执行 | ❌ |
| RUNNING | 执行中 | ❌ |
| PAUSED | 已暂停（可恢复） | ❌ |
| COMPLETED | 执行完成 | ✅ |
| FAILED | 执行失败 | ✅ |
| CANCELLED | 用户取消 | ✅ |

> **注**：PAUSED 状态用于支持"中断后恢复"（Pause & Resume）。后续节点5-6（Review）可循环迭代直至 APPROVED 状态。

### Early Exit 条件

在节点2（可行性分析）中，若评估为不可行，系统应：

1. 终止后续工作流
2. 输出《可行性分析报告》，说明不可行的原因
3. 向用户发送终止通知

---

## 1.3 学科领域支持

### 预设学科领域

| 领域代码 | 学科名称 |
|:---:|---|
| CS | 计算机科学 |
| GEO | 地理学 |
| RS | 遥感科学 |
| GEOL | 地质学 |
| PHYS | 物理学 |
| MATH | 数学 |
| CHEM | 化学 |
| BIO | 生物学 |
| MED | 医学 |
| ECON | 经济学 |

> **扩展性**：系统应支持通过配置文件扩展学科领域。

### 文档类型支持

| 类型代码 | 文档类型 |
|:---:|---|
| PAPER | 学术论文 |
| PATENT | 专利申请书 |
| ABSTRACT | 摘要 |
| SURVEY | 调研报告 |
| PROPOSAL | 项目提案 |
| THESIS | 学位论文 |

---

## 1.4 产出物定义

### 产物清单

| 节点 | 产出物 | 格式 | 描述 |
|:---:|---|---|---|
| 2 | 《可行性分析报告》 | JSON/Markdown | 包含创新性评估、原创性评估、可行性结论 |
| 3 | 《文献综述与资源列表》 | Markdown | 按学科分类的文献摘要与链接列表 |
| 4 | 《初稿文档》 | Markdown/LaTeX | 基于模板的初始文档 |
| 5-6 | 《评审意见》 | JSON | 逻辑问题列表、重复率报告 |
| 7 | 《终稿文档》 | Markdown/LaTeX | 去AI化处理后的终稿 |
| 8 | 《最终文档》 | Markdown/PDF | 排版后的可交付文档 |

### JSON Schema 定义

#### Feasibility Object

```json
{
  "feasibility": "PASS | FAIL",
  "innovativeness": {
    "score": 0-10,
    "analysis": "string"
  },
  "originality": {
    "score": 0-10,
    "analysis": "string",
    "references": ["url1", "url2"]
  },
  "researchValue": {
    "score": 0-10,
    "analysis": "string"
  },
  "riskAssessment": [
    {
      "risk": "string",
      "probability": "LOW | MEDIUM | HIGH"
    }
  ],
  "conclusion": "string",
  "earlyExit": true | false
}
```

> **注**：`researchValue` 和 `riskAssessment` 字段详见 `03_Multi_Agent_Topology.md` 第278-287行。

#### Review Object

```json
{
  "logicValidation": {
    "passed": true | false,
    "issues": [
      {
        "location": "section 3.2",
        "problem": "string",
        "severity": "HIGH | MEDIUM | LOW"
      }
    ]
  },
  "plagiarismCheck": {
    "passed": true | false,
    "similarityRate": 0.0-100.0,
    "sources": [
      {
        "url": "string",
        "similarity": 0.0-100.0
      }
    ]
  }
}
```

---

## 1.5 用户交互规范

### 输入字段

| 字段 | 必填 | 描述 |
|:---:|:---:|---|
| topic | 是 | 研究主题/论文题目 |
| domain | 是 | 学科领域 |
| docType | 是 | 文档类型 |
| template | 否 | 用户提供的模板/大纲 |
| requirements | 否 | 特殊要求/约束 |

### 输出通知

| 阶段 | 通知内容 |
|:---:|---|
| 开始 | "任务已接受，正在进行意图分析..." |
| 节点2 | "正在进行可行性分析..." |
| 节点3 | "正在进行深度调研..." |
| 节点4 | "正在起草文档..." |
| 节点5-6 | "正在进行评审..." |
| 节点7 | "正在进行润色..." |
| 完成 | "任务已完成！文档保存在: {path}" |
| Early Exit | "任务终止。原因: {reason}" |

> **注**：通知应通过 SSE (Server-Sent Events) 流式推送至前端。

---

## 1.6 工作流配置

### 超时配置

| 节点 | 建议超时 | 说明 |
|:---:|:---:|---|
| 1. Intent Analysis | 30s | 轻量级解析 |
| 2. Feasibility Study | 2min | 需要网络搜索 |
| 3. Deep Research | 5min | 需要深度文献检索 |
| 4. Drafting | 3min | 生成初稿 |
| 5-6. Review | 2min | 逻辑+查重 |
| 7. Polishing | 2min | 去AI化处理 |
| 8. Publishing | 30s | 生成最终文档 |

### 重试策略

| 节点 | 最大重试次数 | 回退策略 |
|:---:|:---:|---|
| 2 | 2 | 更换搜索API |
| 3 | 2 | 扩展搜索关键词 |
| 4 | 1 | 更换模型 |
| 5-6 | 3 | 迭代修复 |
| 7 | 1 | 更换提示词策略 |

---

*Last Updated: 2026-05-03*