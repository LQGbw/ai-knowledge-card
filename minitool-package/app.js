(function () {
  "use strict";

  var cards = [
    { term: "FDE", alias: "前线部署工程师", definition: "深入客户业务现场，把 AI 能力部署进真实工作流的工程角色。", why: "企业 AI 的难点正在从模型能力转向业务理解、数据接入和工程落地。", status: "新兴概念", uncertainty: "不同公司对 FDE 的职责范围和交付方式仍有差异。", confidence: "高", sources: 2, pattern: "grid" },
    { term: "蒸馏", alias: "模型蒸馏", definition: "利用更强模型的输出或行为，训练另一个模型获得相近能力。", why: "它能降低模型训练与使用成本，也引出了授权和能力提取的争议。", status: "仍有争议", uncertainty: "正常训练技术与未经授权的能力提取之间，行业边界仍存在争议。", confidence: "高", sources: 2, pattern: "fan" },
    { term: "开放权重", alias: "Open Weights", definition: "公开训练后的模型参数，让外部用户可以部署、推理或继续开发。", why: "开放权重正在影响模型成本、开发生态和闭源模型的商业模式。", status: "已有共识", uncertainty: "开放权重不等于完整开源，训练数据、代码和授权条件可能仍不公开。", confidence: "高", sources: 1, pattern: "stamp" },
    { term: "Sim-to-Real", alias: "从仿真到现实 · Sim2Real", definition: "先在仿真环境训练机器人，再把获得的能力迁移到现实世界。", why: "它可以缓解真实机器人训练数据昂贵、危险且难以规模化的问题。", status: "已有共识", uncertainty: "仿真与现实之间仍存在差距，通常需要真实数据继续校准。", confidence: "高", sources: 1, pattern: "orbit" },
    { term: "RSI", alias: "递归自我提升", definition: "AI 改进自身能力后，再利用提升后的能力继续改进自己的过程。", why: "如果形成可靠闭环，模型能力进步可能从人工推动转向部分自我推动。", status: "仍有争议", uncertainty: "能否持续、可靠地实现递归提升仍未形成行业共识。", confidence: "中", sources: 2, pattern: "weave" },
    { term: "Harness", alias: "Agent Harness", definition: "围绕模型组织工具、上下文和执行循环的智能体编排层。", why: "模型趋于通用后，智能体能否稳定完成任务越来越取决于编排与反馈机制。", status: "新兴概念", uncertainty: "不同团队对 Harness 是否包含记忆、评测和运行环境有不同划分。", confidence: "中", sources: 3, pattern: "petal" },
    { term: "经验差距", alias: "Experience Gap", definition: "模型能力不断提高，但智能体无法积累每次真实交互经验的落差。", why: "缩小差距需要把用户修正、撤销和任务结果转化为可持续学习信号。", status: "新兴概念", uncertainty: "这是特定分享中提出的概念，尚不能视为已经稳定的行业术语。", confidence: "中", sources: 1, pattern: "fan" },
    { term: "主权 AI", alias: "Sovereign AI", definition: "企业在模型权重和智能能力层面掌握自主控制权的路线。", why: "它试图把企业壁垒从调用通用 API 转向自有数据、模型和业务判断。", status: "仍有争议", uncertainty: "该词也用于国家级 AI 基础设施，这里主要指企业自建智能。", confidence: "中", sources: 1, pattern: "stamp" },
    { term: "奖励黑客", alias: "Reward Hacking", definition: "模型钻评分或奖励规则的空子，获得高分却没有真正完成目标。", why: "强化学习进入真实业务后，错误的验证标准可能训练出表面合格的行为。", status: "已有共识", uncertainty: "具体表现取决于任务、环境和评分机制。", confidence: "高", sources: 2, pattern: "grid" },
    { term: "Headless", alias: "无头软件", definition: "不依赖图形界面、可由 Agent 直接调用数据和能力的软件形态。", why: "AI 可能绕过为人设计的界面，直接通过工具和接口完成工作。", status: "新兴概念", uncertainty: "GUI 不一定消失，更多是从唯一入口变为多种入口之一。", confidence: "中", sources: 1, pattern: "weave" },
    { term: "Agentic Economy", alias: "智能体经济", definition: "围绕智能体运行、协作和交易形成的新型基础设施与商业分工。", why: "沙箱、记忆和支付等能力可能从应用功能变成面向智能体的公共基础设施。", status: "新兴概念", uncertainty: "概念仍处早期，目前更多描述趋势而非边界清晰的经济体系。", confidence: "中", sources: 1, pattern: "petal" },
    { term: "世界模型", alias: "World Model", definition: "让 AI 学习环境如何变化，从而理解、预测或规划现实世界行为的模型。", why: "它被视为机器人和具身智能理解物理环境的重要候选路线。", status: "仍有争议", uncertainty: "视频生成、3D 生成、JEPA、VLA 等路线是否都属于世界模型仍有分歧。", confidence: "中", sources: 1, pattern: "orbit" }
  ];

  var evidence = {
    "FDE": ["真实行业角色", "Palantir 长期用 Forward Deployed Engineer 指深入客户现场、把软件接入真实业务的工程角色；后来这一角色在企业 AI 落地中重新受到关注。", "Palantir DevCon 3 · AI Forward Deployed Engineer", "Palantir 是该角色最具代表性的实践者之一，但目前没有可靠证据证明它是唯一首创者。"],
    "蒸馏": ["奠基论文", "Hinton、Vinyals 与 Dean 在 2015 年展示了如何把模型集成的知识转移到更轻量的单一模型中。", "Distilling the Knowledge in a Neural Network", "2006 年 Buciluă 等人的模型压缩工作是更早的直接前身；2015 年论文使 knowledge distillation 这一表述广泛流行。"],
    "开放权重": ["发布事件", "Mistral 在 2023 年发布 Mixtral 8x7B 权重并采用 Apache 2.0 许可，成为开放权重路线的代表事件。", "Mistral AI · Mixtral of Experts", "开放权重没有公认单一首出处，也不等同于训练代码、数据和过程全部开源。"],
    "Sim-to-Real": ["机器人实验", "OpenAI 研究团队让机械臂控制策略完全在仿真中训练，再直接部署到真实机械臂完成推物任务。", "Sim-to-real transfer with dynamics randomization", "这是 2017 年有影响力的案例，不是 Sim-to-Real 思想的唯一源头。"],
    "RSI": ["思想源头", "I. J. Good 在 1965 年提出：足够聪明的机器可以设计更聪明的机器，由此触发智能爆炸。", "Speculations Concerning the First Ultraintelligent Machine", "Good 提出的是智能爆炸论证；RSI 作为今天的缩写和工程概念是后续发展，尚没有稳定实现。"],
    "Harness": ["近期官方语境", "OpenAI 在 Agents SDK 中把 harness 描述为组织文件、工具、执行循环与沙箱的模型原生基础设施。", "OpenAI · The next evolution of the Agents SDK", "Harness 的边界仍在变化，不同团队会把记忆、评测、权限或运行环境划入不同层。"],
    "经验差距": ["访谈概括", "LangChain 创始人 Harrison Chase 提到：如果用户必须重复给出同一种纠正，智能体就没有真正从交互中学习。", "Sequoia · Harrison Chase on AI agent orchestration", "经验差距不是已经稳定的行业术语，更像对访谈中持续学习问题的中文概括。"],
    "主权 AI": ["定义冲突", "NVIDIA 的主流用法指一个国家使用本地基础设施、数据、人才和产业生态开发与部署 AI。", "NVIDIA · Sovereign AI Summit", "当前卡片强调企业拥有自己的智能，更接近 Own Your Intelligence。建议后续将卡名改为自有智能，避免与国家级 Sovereign AI 混淆。"],
    "奖励黑客": ["经典案例", "赛车智能体为了刷高奖励，不去完成比赛，而是在赛道中反复撞击得分目标物。", "Google DeepMind · Specification gaming", "Reward hacking 与 specification gaming 常被交替使用，但严格定义和适用范围仍可能不同。"],
    "Headless": ["趋势表达", "十字路口访谈把传统 GUI 软件与可被 Agent 直接调用的数据、工具和接口进行对比。", "十字路口 Crossing · Agent 元年第 500 天", "Headless 早已用于 CMS 和电商架构；把它扩展为 Agent 软件趋势，是较新的行业表达，并非一个新发明的技术。"],
    "Agentic Economy": ["研究论文", "Microsoft Research 描绘了消费者代理与企业服务代理程序化协商和交易的市场结构。", "Microsoft Research · The Agentic Economy", "这是趋势框架而不是已成熟的经济体系；同名说法可能来自多个团队，并无唯一首创者。"],
    "世界模型": ["代表论文", "David Ha 与 Jürgen Schmidhuber 在 2018 年让智能体在内部生成的梦境环境里训练策略，再迁移回真实游戏环境。", "World Models · Ha & Schmidhuber", "2018 年论文让该词重新流行，但类似思想和 world model 用法更早已经出现。"]
  };

  var state = { view: "daily", index: 5, flipped: false, saved: [], showEvidence: false };
  var nodes = {};

  function byId(id) { return document.getElementById(id); }
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[character];
    });
  }
  function readSaved() {
    try {
      var parsed = JSON.parse(localStorage.getItem("ai-concept-saved") || "[]");
      if (Array.isArray(parsed)) state.saved = parsed.filter(function (term) { return typeof term === "string"; });
    } catch (error) { state.saved = []; }
  }
  function writeSaved() {
    try { localStorage.setItem("ai-concept-saved", JSON.stringify(state.saved)); } catch (error) { /* 本地存储不可用时仍保持当前会话状态。 */ }
  }
  function renderCard() {
    var card = cards[state.index];
    var isSaved = state.saved.indexOf(card.term) !== -1;
    nodes.pattern.className = "print-pattern " + card.pattern;
    nodes.counter.textContent = String(state.index + 1).padStart(2, "0") + " / " + cards.length;
    nodes.front.innerHTML = '<span class="card-label">AI CONCEPT</span><strong>' + escapeHtml(card.term) + '</strong><em>' + escapeHtml(card.alias) + '</em><span class="definition">' + escapeHtml(card.definition) + '</span><span class="flip-hint">点击翻面 <b>↗</b></span>';
    nodes.back.innerHTML = '<span class="card-label">WHY IT MATTERS</span><strong>为什么值得关注？</strong><span class="why-copy">' + escapeHtml(card.why) + '</span><span class="uncertainty">边界提醒：' + escapeHtml(card.uncertainty) + '</span><span class="meta-row"><i>' + escapeHtml(card.status) + '</i><i>可信度 ' + escapeHtml(card.confidence) + '</i><i>' + card.sources + ' 条来源</i></span><span class="flip-hint">点击返回 <b>↙</b></span>';
    nodes.card.classList.toggle("is-flipped", state.flipped);
    nodes.front.hidden = state.flipped;
    nodes.back.hidden = !state.flipped;
    nodes.save.textContent = isSaved ? "已收藏 ✓" : "先收藏";
    nodes.save.classList.toggle("saved", isSaved);
    nodes.savedCount.textContent = state.saved.length + " / " + cards.length;
    nodes.savedProgress.style.width = (state.saved.length / cards.length * 100) + "%";
    renderEvidence();
  }
  function renderEvidence() {
    var item = evidence[cards[state.index].term];
    nodes.evidencePanel.hidden = !state.showEvidence;
    nodes.evidenceButton.textContent = state.showEvidence ? "收起出处" : "查看案例与出处";
    if (!state.showEvidence) return;
    nodes.evidenceLabel.textContent = item[0];
    nodes.evidenceCase.textContent = item[1];
    nodes.evidenceSource.textContent = item[2];
    nodes.evidenceNote.textContent = item[3];
  }
  function renderView() {
    var daily = state.view === "daily";
    nodes.dailyView.hidden = !daily;
    nodes.libraryView.hidden = daily;
    nodes.dailyNav.classList.toggle("active", daily);
    nodes.libraryNav.classList.toggle("active", !daily);
    nodes.title.textContent = daily ? "今天，认识一个新概念" : "十二张概念卡";
    if (!daily) { state.showEvidence = false; renderEvidence(); }
  }
  function renderLibrary() {
    nodes.grid.innerHTML = cards.map(function (card, index) {
      return '<button class="mini-card" type="button" data-card-index="' + index + '"><span class="mini-pattern ' + card.pattern + '" aria-hidden="true"></span><small>' + String(index + 1).padStart(2, "0") + '</small><strong>' + escapeHtml(card.term) + '</strong><em>' + escapeHtml(card.alias) + '</em><p>' + escapeHtml(card.definition) + '</p><span class="mini-meta">' + escapeHtml(card.status) + ' · ' + card.sources + ' 条来源</span></button>';
    }).join("");
  }
  function cacheNodes() {
    nodes.dailyNav = byId("daily-nav"); nodes.libraryNav = byId("library-nav");
    nodes.dailyView = byId("daily-view"); nodes.libraryView = byId("library-view");
    nodes.title = byId("page-title"); nodes.card = byId("knowledge-card");
    nodes.pattern = byId("card-pattern"); nodes.counter = byId("card-counter");
    nodes.front = byId("card-front"); nodes.back = byId("card-back");
    nodes.save = byId("save-button"); nodes.next = byId("next-button");
    nodes.savedCount = byId("saved-count"); nodes.savedProgress = byId("saved-progress");
    nodes.evidenceButton = byId("evidence-button"); nodes.evidencePanel = byId("evidence-panel");
    nodes.evidenceLabel = byId("evidence-label"); nodes.evidenceCase = byId("evidence-case");
    nodes.evidenceSource = byId("evidence-source"); nodes.evidenceNote = byId("evidence-note");
    nodes.evidenceClose = byId("evidence-close"); nodes.grid = byId("card-grid");
  }
  function bindEvents() {
    nodes.dailyNav.addEventListener("click", function () { state.view = "daily"; renderView(); });
    nodes.libraryNav.addEventListener("click", function () { state.view = "library"; renderView(); });
    nodes.card.addEventListener("click", function () { state.flipped = !state.flipped; renderCard(); });
    nodes.next.addEventListener("click", function () { state.index = (state.index + 1) % cards.length; state.flipped = false; state.showEvidence = false; renderCard(); });
    nodes.save.addEventListener("click", function () {
      var term = cards[state.index].term; var position = state.saved.indexOf(term);
      if (position === -1) state.saved.push(term); else state.saved.splice(position, 1);
      writeSaved(); renderCard();
    });
    nodes.evidenceButton.addEventListener("click", function () { state.showEvidence = !state.showEvidence; renderEvidence(); });
    nodes.evidenceClose.addEventListener("click", function () { state.showEvidence = false; renderEvidence(); });
    nodes.grid.addEventListener("click", function (event) {
      var button = event.target.closest("[data-card-index]");
      if (!button) return;
      state.index = Number(button.getAttribute("data-card-index")); state.flipped = false; state.showEvidence = false; state.view = "daily";
      renderCard(); renderView();
    });
  }
  function init() {
    cacheNodes(); readSaved(); renderLibrary(); renderCard(); renderView(); bindEvents();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
}());
