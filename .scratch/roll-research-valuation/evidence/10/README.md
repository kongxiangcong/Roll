# 10 独立公司报告页面与共享联动

10实现及当前真实复用路径验收完成。用户可从主导航“公司研报”输入已登记公司名称/代码，显式解决歧义，选择截至时间、刷新或复用材料，启动/取消/重试任务；也可直接复用历史已发布报告，不重新调用模型。报告正文按React文本、标题和表格安全呈现，来源HTML不会执行；图只接受固定报告图表端点。PDF/Markdown及引用、估值、输入、manifest链接绑定具体交付版本，渲染失败保留正文，重试追加新文件版本。

报告与日常研究通过company_id、snapshot_id及core_sha256关联。报告可打开同快照公司跟踪并返回同快照报告。独立跟踪只读，不自动加入持仓/关注、不触发来源刷新或模型；日常页原更新行为保留。当前报告与请求快照不同时明确提示。当前重建旧资料不冒充历史PIT，未来截至时间拒绝，页面读取不刷新旧研究时点。

## 已运行验证

- 公开网页TDD逐切片记录见[commands.md](commands.md)。最后[green08-active-job.txt](green08-active-job.txt)为PASS：身份歧义、未来时间、任务进度/取消/重试、来源及模型不可用保留正文、安全HTML文本、PDF失败/重试、手机无整页溢出、共享只读深链、无资料、公司隔离和重载恢复。查看旧报告原任务不能覆盖新任务的重载指针，red08先复现、最小修复后通过。
- [regression07-daily.txt](regression07-daily.txt)为PASS：默认每日路径公司切换、固定历史、更新失败/重试和重载均通过，3次METHOD更新。新截图保存为本票regression07-*，原07截图逐字恢复，未把新结果写成07旧实证。
- [build-final08.txt](build-final08.txt)：tsc/Vite通过。保留大于500kB产物提示，没有调高阈值隐藏提示。没有后端产品代码改动，未重复后端宽suite/模型调用。

## 真实浏览器与历史模型分账

实际IAB在本票独立5210/8030访问`rv10-real01`：输入000848→承德露露身份→明确复用已发布PARTIAL报告→原任务/进度→完整正文和质量缺口→实际下载MD/PDF→切换文件历史→固定共享快照跟踪→返回报告。实际桌面/390px截图及DOM在本目录；根代理独立只读验收见[independent-root-ui-check.md](independent-root-ui-check.md)。

报告`b9cfb2a0-8f93-516a-a4cd-7b7801fd7911`，原job`cf414530-5dee-45d3-af28-0e7e3f9321ae`，snapshot`7a430e8b-4172-4598-af21-6fe8600b6b93`，core`37b71966590cb1cb8d0c2898c4bace4c7ec1bc3b216018d2f941204f22dcac1d`，12宿主章节COMPLETE，研究PARTIAL。模型事实沿用08真实CODEX原件/复核记录（8旧raw复用+4新实际请求），不是10网页新触发模型；来源沿用05/08真实披露和外部估值输入，没有10新公网采集。不能据此宣称已补全A6资料或12两个盘后周期。

[real-final-receipt.json](real-final-receipt.json)验证原report和delivery完整对象与09副本相等，账户均0。网页真实下载位于downloads/，MD134450 bytes/SHA`3970917631045c9c5a0ed88651849a8f2775b8a2d90711b8c0bdd2ebbc032720`，PDF364172 bytes/45页/SHA`b135d59a72287ea6f998fd591882cc28de078f745741b7bc6d225ec1d7ddf408`，与固定归档逐字一致。没有重新渲染、修改PDF或旧报告。

另在真实网页创建新task`2c427d2d-0dda-4f5d-9c6f-ea7de8303995`，QUEUED→CANCELLED→显式retry→QUEUED→最终CANCELLED，0sections/input_id=null。隔离host为API-only，没有worker/模型执行；此记录只证明真实请求和任务控制，不冒称新CODEX生成报告。MODEL/SOURCE不可用、无资料/歧义/渲染失败负例用METHOD独立验证。

## 真实失败与修复

首次独立跟踪复用每日组件，未入关注名单的公司产生`OBSERVATION_NOT_IN_HOLDINGS_OR_WATCHLIST`并显示不能使用的更新控件；原red DOM/截图保留，修复为独立只读模式，正常日常默认行为回归通过。真实IAB的getByLabel严格匹配文件下拉定位失败后按新DOM用combobox角色定位，文件历史切换成功；不是产品错误或绕过。最早METHOD默认日常接口夹具缺members等响应导致DOM脱离；夹具错误与真实实现红灯分列。编译曾发现unknown不能作为ReactNode，修Boolean守卫，失败输出保留。

## 启动与下一票

API-only8030：显式PYTHONPATH指本工作树backend/src、明确store，serve_api.py记录module-paths；不加载.env/不启动worker。API launcher45612、实际listener25036及ticks见api-receipt.json。Vite5210 PID50308见web-receipt.json。为后续验证保持服务运行；原07/08/09/生产服务未改。临时IAB仅本票tab已关闭，390px临时viewport已恢复。

资料/用途缺口保持：CURRENT_PRICING blocked、BASELINE_RESEARCH conditional、非严格历史PIT，真实行业/同行/图等不足。10只关闭本票工程与复用网页路径；11只读研究特征及12真实联合矩阵仍按序待做，整体功能未完成。用法见docs/research/company-report-workflow.md。
