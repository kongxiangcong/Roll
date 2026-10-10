# 凭据补充后的最终集成验收

日期：2026-10-08。分支 `codex/roll-p0-integration`；本轮固定起点 `d1b867e`。最终产品/测试修复 `db9ef0c8da4f9e00215e26f06baa79d924a4183b`，合入 `6ad9928c71ebc0b3ffd59fcf8c9f25fdfc4c9461`；独立合入记录 `036cbd6` 及其后仅新增文档/证据。本次完整后端和默认Chrome开始前冻结产品、测试及依赖，执行期间没有改源码。根目录与 `db9ef0c` 的 backend/src、backend/tests、frontend/src、frontend/tests、frontend/scripts 和锁文件差异为零。

## 最终结果

| 验证 | 本次实际结果 | 原输出/报告 |
|---|---|---|
| 根完整后端 | 372通过、0失败、0跳过；1501.96秒；退出码0 | [pytest stdout](final-backend-db9ef0c.txt) |
| 默认Chrome，12文件逐文件空SQLite隔离 | 16通过、3按profile跳过、0失败、0flaky；退出码0 | [启动/结束与统计](browser-default/manifest.json)、[完整stdout](final-default-browser.txt)；目录内保留各文件results.json/stdout.txt |
| 根TypeScript/Vite | 类型检查及构建通过，54模块 | [构建输出](merge-review-fixes-build.txt) |
| 独立合并接缝 | 6通过、35.52秒；与完整套件不累加 | [接缝结果](merge-review-fixes-focused.txt)、[合入核对](merge-review-fixes.md) |
| 双轴审阅 | 原Standards 1项P2、Spec 1项P2均解决，两轴复核无新增问题 | [完整分轴与修复](review.md) |

完整后端命令为根锁定 `backend/.venv/Scripts/python.exe -B -X utf8 -u -m pytest -v`，cwd根backend，PYTHONPATH指向根backend/src，Python3.13.12/pytest9.0.2；设置ROLL_ENV=test，移除模型/扶摇凭据、认证/env文件及live profile变量。该整套使用METHOD固定响应、公开FastAPI和隔离真实SQLite，不发真实付费模型请求，不作为新增实际来源/模型验收。

默认Chrome执行 `npm run test:e2e`，API8490/web5490，ROLL_ENV=test且无实际凭据/live profile；UTC05:17:36.789开始、05:20:12.751结束，155.962秒。三个跳过分别为backend-switch真实归档profile、DeepSeek外部SDK方法profile、已有真实来源估值profile；实际模型/外部来源页面另见票级证据，默认离线组合不替代它们。

## 原失败与修复边界

本轮旧代码基线[340通过/3失败](baseline-backend.md)：三例METHOD消费钟与实际收件墙钟不一致，采用显式推进的测试时钟修复，生产门禁及原断言不变。第一轮新集成[366通过/1失败](integrated-backend-first.md)及[原stdout](final-backend-a7de463.txt)仍保留：增加四个宽基背景后，旧共享4次预算不能取得全部日线/报价。

同一个修复实现者处理两轴问题和背景回归：子请求继承除权来源；市场拥有并明确注入类型化档案复用查询，对已持久化source_revisions权威hash检查修订，旧审计不回写；四宽基日线/报价与持仓共享8次取数，原期限/总字节/三次停止/退避不变，模型8工具/6取数硬帽不变。公开接口红绿、90项早期相关组合与25项最后组合分层记录于[修复证据](review-fixes.md)，不能相加为完整计数。最终本次372项单轮全绿。

## 交付与未完成条件

- 12实际DeepSeek多轮、关联任务、截断、取消、合成无效key的401、宿主硬崩恢复及Chrome归档/零联网回放：[真实验收](../12/live-acceptance.md)。资料仍PARTIAL，引用验证不等于事实充分或cutoff可用。
- 13实际双向切换、配置冻结、同问题关联重试、30持仓/5固定指数容量、取消/超时、两实际模型对受控越权材料的拒绝及Chrome档案：[逐项验收](../13/acceptance.md)。两方向各100次确认P95为591.4442/616.9941ms；完整RUNNING重叠仅39/5次，分别205.7219/61.6667ms。其余样本及较早30+3结果分列，不能扩大并行证据。
- 扶摇实取600519的908原价/908当前前复权日线、7除权事件，新增沪深300/中证500使固定背景共5个：[来源验收](../fuyao/acceptance.md)、[背景补充](../fuyao/background-acceptance.md)。批次报价时点不充当证券自身时点，未取得历史PIT/当前特殊状态/完整公司行为或账户权益确认。
- 19仍needs-info/partial：原120标签实际DEV0/CAL0、校准支持不足、封存独立性UNPROVEN和输入暴露保留。20、21、23—34等待实际依赖；不调低阈值、不生成真实模型/概率、不启用正式能力或真实前向验证。

必要实际/受控案例运行文件851份、778,429,430字节由四份merge-runtime清单保全到根ignored运行目录；[清理前哈希/凭据核验](final-preservation.json)与[核验脚本](verify-preservation.py)逐SHA256/长度检查，.env原样、忽略且未跟踪，凭据零匹配。完整测试临时DB不永久复制，原stdout和必要案例档案保留。

四个自有干净、已合入的实现工作树已按implement-spec第9步清理，分支/提交全部保留。准确路径/HEAD、四个仅解除本身的依赖junction、根Python与Playwright CLI清理前后相同SHA见[清理核对](worktree-cleanup-final.json)及[执行脚本](cleanup-worktrees.ps1)。Git仅剩集成根工作树；[清理后目标副本复验](final-preservation-after-cleanup.json)依据原清单检查全部851文件，源检出已清理所以该次明确为DESTINATION_ONLY。仅本地提交，无推送/PR。
