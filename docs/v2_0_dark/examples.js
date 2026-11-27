"use strict";

// Conceptual teaching examples; these are not live model outputs or benchmark traces.
window.AGENTDOG_EXAMPLES = [
  {
    id: "goal",
    acronym: "CGM",
    category: {
      en: "Covert goal manipulation",
      zh: "隐蔽目标操纵",
    },
    illustrative: true,
    disclaimer: {
      en: "Conceptual illustration. No live model is called; no experimental outcome is claimed.",
      zh: "概念示例，不调用在线模型，也不代表实验结果。",
    },
    title: {
      en: "A hidden requirement redirects the task.",
      zh: "隐藏的前置要求，悄悄改变任务目标。",
    },
    task: {
      en: "Summarize internal project notes and keep the source material inside the workspace.",
      zh: "总结内部项目笔记，并将所有原始资料保留在工作区内。",
    },
    steps: [
      {
        label: { en: "Read local notes", zh: "读取本地笔记" },
        kind: "safe",
      },
      {
        label: { en: "Retain injected requirement", zh: "保留注入的要求" },
        kind: "risk",
      },
      {
        label: { en: "Propose external upload", zh: "提出向外部上传" },
        kind: "risk",
      },
      {
        label: { en: "Intercept before transfer", zh: "传输前拦截" },
        kind: "blocked",
      },
    ],
    source: {
      en: "An untrusted retrieved note presents an external validation step as a task prerequisite.",
      zh: "不可信的检索笔记，将外部验证步骤包装成完成任务的前置条件。",
    },
    failure: {
      en: "The agent treats content as authority and carries the unrelated requirement into a later decision.",
      zh: "智能体将资料内容误当成授权，并把无关要求带入后续决策。",
    },
    harm: {
      en: "Internal information could leave the approved workspace.",
      zh: "内部信息可能离开授权工作区。",
    },
    proposedAction: {
      en: "Upload the original notes to an external service for supposed validation.",
      zh: "为完成所谓的验证，将原始笔记上传至外部服务。",
    },
    guardDecision: {
      en: "Intercept the transfer: it conflicts with the user's local-only instruction.",
      zh: "拦截传输：该动作违反用户仅保留在本地的要求。",
    },
    safeAlternative: {
      en: "Ignore the embedded requirement and produce the requested summary locally.",
      zh: "忽略资料中夹带的要求，在本地生成用户需要的总结。",
    },
  },
  {
    id: "authority",
    acronym: "AOV",
    category: {
      en: "Authority and obligation violations",
      zh: "权限与义务违反",
    },
    illustrative: true,
    disclaimer: {
      en: "Conceptual illustration. No live model is called; no experimental outcome is claimed.",
      zh: "概念示例，不调用在线模型，也不代表实验结果。",
    },
    title: {
      en: "An earlier approval becomes stale.",
      zh: "曾经的审批，已经失效。",
    },
    task: {
      en: "Prepare a revised shared report while respecting the current access policy.",
      zh: "准备共享报告的修订内容，并遵守当前的访问策略。",
    },
    steps: [
      {
        label: { en: "Receive initial approval", zh: "获得初始审批" },
        kind: "safe",
      },
      {
        label: { en: "Write permission revoked", zh: "写入权限被撤销" },
        kind: "risk",
      },
      {
        label: { en: "Reuse the stale approval", zh: "沿用过期审批" },
        kind: "risk",
      },
      {
        label: { en: "Require current authority", zh: "检查当前授权" },
        kind: "blocked",
      },
    ],
    source: {
      en: "Retained approval no longer matches the current permission state.",
      zh: "保留的历史审批，与当前权限状态不再一致。",
    },
    failure: {
      en: "The agent relies on an earlier authorization after write access has been withdrawn.",
      zh: "写入权限被撤销后，智能体仍依赖先前的授权。",
    },
    harm: {
      en: "A shared artifact could be changed without current authorization.",
      zh: "共享文件可能在缺乏当前授权的情况下被修改。",
    },
    proposedAction: {
      en: "Overwrite the shared report using the approval retained from an earlier stage.",
      zh: "依据先前阶段保留的审批，覆盖共享报告。",
    },
    guardDecision: {
      en: "Hold the write: the proposed change needs valid authorization under the current policy.",
      zh: "暂停写入：候选修改需要满足当前策略下的有效授权。",
    },
    safeAlternative: {
      en: "Keep the revision as a local draft and seek current authorization before changing the shared file.",
      zh: "先将修订保留为本地草稿，获得当前有效授权后再修改共享文件。",
    },
  },
  {
    id: "control",
    acronym: "LoC",
    category: {
      en: "Loss of control",
      zh: "失控风险",
    },
    illustrative: true,
    disclaimer: {
      en: "Conceptual illustration. No live model is called; no experimental outcome is claimed.",
      zh: "概念示例，不调用在线模型，也不代表实验结果。",
    },
    title: {
      en: "Retries continue beyond the stop condition.",
      zh: "反复重试，越过了停止条件。",
    },
    task: {
      en: "Run a bounded diagnostic check and stop when the retry limit is reached.",
      zh: "执行有边界的诊断检查，并在达到重试上限时停止。",
    },
    steps: [
      {
        label: { en: "Start bounded diagnostics", zh: "开始有界诊断" },
        kind: "safe",
      },
      {
        label: { en: "Repeated failures accumulate", zh: "重复失败逐渐积累" },
        kind: "risk",
      },
      {
        label: { en: "Propose retry after limit", zh: "达到上限后仍拟重试" },
        kind: "risk",
      },
      {
        label: { en: "Enforce the stop condition", zh: "执行停止条件" },
        kind: "blocked",
      },
    ],
    source: {
      en: "Accumulated execution errors and repeated replanning obscure the stopping rule.",
      zh: "执行错误不断积累，反复重规划使停止规则被忽略。",
    },
    failure: {
      en: "The agent continues execution after the explicit retry boundary has been reached.",
      zh: "达到明确的重试边界后，智能体仍继续执行。",
    },
    harm: {
      en: "Unnecessary continued execution could consume resources and prolong an uncontrolled workflow.",
      zh: "不必要的持续执行可能消耗资源，并延长失控的工作流。",
    },
    proposedAction: {
      en: "Start another diagnostic attempt despite the already satisfied stop condition.",
      zh: "在停止条件已经满足的情况下，再发起一次诊断尝试。",
    },
    guardDecision: {
      en: "Block further execution and honor the declared stopping boundary.",
      zh: "阻止进一步执行，遵守已声明的停止边界。",
    },
    safeAlternative: {
      en: "Stop tool use and report the partial result and unresolved failure accurately.",
      zh: "停止调用工具，如实报告部分结果及尚未解决的失败。",
    },
  },
];
