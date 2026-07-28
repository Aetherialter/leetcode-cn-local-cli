# 项目文档索引

本目录集中维护 `leetcode-local-cli` 的项目状态、产品边界、架构、技术决策、开发路线、安全审计和发布资料。根目录 `README.md` 面向使用者；根目录 `AGENTS.md` 是 AI 工具自动发现的开发规则入口，因此不迁入本目录。

## 阅读顺序

当文档内容发生冲突时，按以下顺序判断：

1. [产品边界与待定决策](PRODUCT_BOUNDARIES.md)：已经确认的用户可见行为和实施前必须决定的问题。
2. [项目状态](PROJECT_STATUS.md)：当前源码已经实现和验证的能力。
3. [当前架构](ARCHITECTURE.md)：真实模块职责、依赖方向和数据流。
4. [长期开发计划](DEVELOPMENT_PLAN.md)：唯一的实施路线、优先级和阶段目标。
5. [v1.0 总体设计大纲](PROJECT_DESIGN.md)：尚未完全落地的长期架构方向。

## 维护资料

- [技术决策记录](TECH_DECISIONS.md)：已采用方案、原因、替代方案和未来调整方向。
- [安全审计与修复清单](SECURITY_REVIEW.md)：当前安全与可靠性风险、修复状态和优先级。
- [发布流程](RELEASING.md)：本地门禁、Trusted Publisher 和标签发布步骤。
- [版本化发布说明](release-notes/)：GitHub Release 使用的版本标题和正文。

旧 `ROADMAP.md` 已删除。它的历史版本记录由 Git 和根目录 README 保留；未来路线统一维护在 `DEVELOPMENT_PLAN.md`，避免两份计划产生冲突。
