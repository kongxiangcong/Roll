# Standards 审查

基线33d2a9c；仅审本次loss_recovery、funding两处扩展、局部路由及测试，排除旧脏文件。未改代码、运行测试或联网。

规范/异味0；原实质P2两项均已关闭：

- 写事务内重读并比较loss_state、data_state、pending及use_check，阻断capture后的状态交错。新增真实capture屏障回归：公开API插入pending draft且account version不变，激活仍409。
- receipt经直接SQL读取check并核验rule原件，绑定scope、peak、funding、account及successor，未递归funding.current。隔离归档损坏回归覆盖current funding、receipt读取和幂等激活409。

历史资金查询不加overlay；旧授权终态、峰值、旧action重放保留，新损失重新latch。REAL分支改读valuation.get(replay=True)并校验账户、权威和日期；本次METHOD证据不证明REAL正向资格。

最终增量：recovery_id/historical_triggered跨边界内峰值增长保留，新触发仍latch；纯计算回归覆盖连续两帧。CapabilityPanel仅向既有GrantCommand传可选已关闭predecessor，未改变旧资格权限。

UI P2已关闭：LossRecoveryPanel仅对明确未提交的CURRENT_CONDITIONS_CHANGED清除pending并重读，允许新检查；未知响应保留原键，其他拒绝仅在读取已验证同check回执后释放。新增浏览器回归覆盖拒绝后刷新、重新检查和实际确认。

只读证据：API 2PASS22.25s；退出前后2PASS29.62s；原Chrome1PASS25.5s，最新build通过。主回归42PASS+旧successor用例失败，基线同失败；补健康monitor fixture后该项1PASS9.22s，未改断言。最新browser-refusal-final.log因测试先unroute后fulfill报Route already handled，拒绝分支浏览器验收待修正拦截后补齐。未重跑。开放产品P2：0。
