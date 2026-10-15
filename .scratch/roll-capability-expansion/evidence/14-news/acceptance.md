# 14 单股新闻列表与HTML原件工程交付

Completion为partial。公开GET/POST /api/market/news/{instrument}及/collect、/runs/{id}、/cancel和单股页面已交付，独立SQLite新闻表、列表/HTML原件先存、幂等/取消/断点恢复可验收。实际AKShare列表与HTML已成功；指定Trafilatura实际正文抽取仍受依赖准备阻塞，不将METHOD合成正文算成真实全文能力。

## 来源、时间与范围

来源akshare-news-em默认关闭，仅SSE:600362观察用途；与已封口的09/10财报来源预算独立。SDK为既有独立环境的AKShare1.19.1，news/news_stock.py SHA fbda1c9a6f5b96552bcd61baa80afb6697fae3ab44ddf659a592b7bcbd1c0ca0，MIT代码，来源数据权益另计。原业务和AKShare依赖未修改。

SDK文档称最近100条，但锁定代码实际pageIndex1/pageSize10/default排序，本票明确显示真实请求范围，不承诺完整历史或时间倒序。最多取得其中3篇正文。标题、列表摘要、原链接、媒体、来源发布时间、列表首次接收、正文原件接收、规范观察可用时间分列；来源未声明时区不补造。提取元数据日期不作首次披露/接收。关联仅搜索关键词线索，后续15处理证券/转载关系。

SDK受限传输丢弃其硬编码示例cookies；每个准备好的请求再移除Cookie/Authorization，包括上游Set-Cookie产生的cookies。禁代理，固定HTTPS域/path/单证券查询，DNS解析结果必须公网，无跳转、无重试。正文原始http链接只作来源记录，限定数字文章路径的实际获取升级为同域https，其他目标不访问。SDK页/范围变化失败关闭。源代码/正文内容均不执行指令。

## 正文与恢复

正文HTML与列表原件不可变保存；正文失败、预算未覆盖、不完整、完整性异常、提取空/失败分别保留标题及缺口，不把摘要作全文。页面仅以文本渲染派生；原链接作文本展示，原件由既有归档下载接口提供。失败/空/取消运行也能展开本次已收到的原件，包括明确标记的不完整前缀及完整性失败接收字节。

18秒采集宿主终止后读取持久journal，已完成列表仍可形成标题观察。60秒离线抽取单独限时、禁止socket连接，未就绪不调用。子进程复用宿主Job，取消/宿主退出终止子进程。死宿主启动恢复只使用已收到字节，不重新HTTP；状态INTERRUPTED。两个初始化器可并行准备不可变候选，但必须在BEGIN IMMEDIATE内重读RUNNING和owner，只有一个提交facts及终态；正常采集也同事务提交。

## 分层验收

- api-red.log：API404原始失败；api-green.log：初次模块导入路径错误，修正后api-green2.log 1通过/8.53秒。
- api-failure.log 2通过/14.07秒；sdk-api.log 3通过/18.68秒：持久化/幂等/重启、摘要全文分开、截至查询、空列表、正文超时、取消、原件SHA，以及实际AKShare组件加METHOD传输的URL限制/302不跟随。零真实HTTP。
- 双审查找到坏BODY原件/标题丢失、Cookie和恢复并发问题。review-red.log 3失败/1通过；review-green.log 4通过/26.13秒。双初始化回归另抓到Ledger显式事务缺少commit，recovery-lock.log 1失败/3通过；修复后recovery-lock-final.log最终4通过/33.18秒。坏BODY保留本次标题/实际接收原件并禁全文；dead-host只恢复一次且不重试。
- browser-red.log：页面尚缺；browser-green.log：测试未展开摘要details，修正定位后browser-final.log 1通过/16.1秒。该正文为METHOD，不是实际Trafilatura。
- source-plan.json单独新来源预算已执行并CLOSED_NO_RETRY：source-attempt.json实际4HTTP、218675字节、10条新闻事实、4份SHA核验原件（1列表+3正文HTML），capture_elapsed_seconds4.039768。账户完全不变；原始实体及journal在actual-source/。source-response.json状态PARTIAL，full_text_verified=false；未重开任何财报或历史预算。
- production-browser.log默认应用读取实际已保存profile，1通过/11.7秒，390px、标题/原HTML/范围提示通过，POST采集0。追加运行原件展开后production-browser-final.log为1通过/13.0秒，build-final.log为最新TypeScript/Vite通过；没有重复真实采集。
- spec-review.md与standards-review.md记录已关闭实质P2；版本和原15脏文件/12旧模型依赖核验见code-versions.json、preservation.json与model-preservation.json。

## 实际全文阻塞

选定Trafilatura2.3.1 Apache-2.0；适配器使用bare_extraction处理已存HTML，独立新venv，业务依赖无变更。runtime-plan.json固定600秒/100MiB/128请求/零重试/只取wheel。

首次dependency-attempt.json于188.034秒因files.pythonhosted.org的dateparser元数据15秒超时CLOSED，未安装。随后明确另记dependency-recovery-plan.json，改为官方元数据锁SHA后本地离线安装；最初误用无pip的业务解释器，导入即失败、未发请求；改用已有新venv后，dependency-recovery-receipt.json于28.962秒/2请求/99000B因TLS握手超时关闭。两者原始日志和计划保留，没有继续重试、换镜像或修改系统代理。

trafilatura-reference.json保持UNAVAILABLE，包完整指纹/实际SDK提取输出/中文真实正文准确性与空页拒判未完成，不接受用标题、摘要或手写抽取替代指定组件。新闻HTML归档成功不等于全文能力完成。15的14完成依赖尚未解除；13仍依赖12真实解析。其余票按既有来源、冻结、资格及时间条件保持阻塞，不推送、不授资格、不改变真实前向起点。

官方依据：[Trafilatura元数据](https://pypi.org/pypi/trafilatura/json)、[核心API](https://trafilatura.readthedocs.io/en/latest/corefunctions.html)。锁定AKShare代码以本地既有1.19.1文件和SHA为准，不用最新网页替换既有组件。
