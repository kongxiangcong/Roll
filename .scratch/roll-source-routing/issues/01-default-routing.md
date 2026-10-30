Status: ready-for-agent
Implementation: complete

# 默认策略、自动回退及对比

实现范围见 ../spec.md。完成后记录实际覆盖及仍未适配的数据类型，不把文档覆盖当运行验收。

## Comments

2026-10-29：默认配置、AUTO有界备用、可选多源比较、研究参考入口与页面已完成。验证见 [validation](../validation.md)，配置及覆盖边界见 [配置说明](../../../docs/data-source-routing.md)。87项原有回归和17项路由/配置测试通过；有限实际取数、比较及零网络回放单列，不代表全市场/历史PIT资格。
