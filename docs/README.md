# 项目文档

根目录 [README](../README.md) 面向使用者；本目录面向维护者。文档按重要性从高到低排列，未实现的长期设想不能覆盖当前源码事实。

## 核心上下文

1. [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前版本、已实现能力、已知问题和下一步。每次开始开发先读。
2. [ARCHITECTURE.md](ARCHITECTURE.md)：当前模块职责、依赖方向、数据流和架构约束。
3. [PRODUCT_BOUNDARIES.md](PRODUCT_BOUNDARIES.md)：已经确认、不得由实现偶然改变的用户行为。
4. [SECURITY_REVIEW.md](SECURITY_REVIEW.md)：凭据、文件写入、用户代码、浏览器和网络边界。

## 执行与参考

5. [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)：只记录当前优先级和近几步，不绑定未来版本号。
6. [TECH_DECISIONS.md](TECH_DECISIONS.md)：影响后续开发的技术选择及关键废弃方案。
7. [PROJECT_DESIGN.md](PROJECT_DESIGN.md)：非承诺性的长期方向；实现前必须重新设计和确认。
8. [RELEASING.md](RELEASING.md)：发布门禁和标签发布流程。
9. [release-notes/](release-notes/)：已发布版本的历史记录，不作为当前设计依据。

## 最小阅读规则

- 普通修复或小功能：读状态、架构、开发计划，再按风险查产品边界或安全审计。
- 跨模块、公开行为、凭据或文件系统改动：同时读产品边界、技术决策和安全审计。
- 长期方向仅用于判断演进空间，不能当作已排期需求。

冲突时按 `PRODUCT_BOUNDARIES → PROJECT_STATUS → ARCHITECTURE → DEVELOPMENT_PLAN → PROJECT_DESIGN` 判断。
