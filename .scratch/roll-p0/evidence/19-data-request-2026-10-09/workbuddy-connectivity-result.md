# WorkBuddy／万得小测试入口核验

结论：本轮只完成调用入口和匿名连通性检查，**没有发出WorkBuddy任务，也没有取得万得行情**。不得将此结果记录为万得取数测试成功／失败。

- 本机存在正在运行的WorkBuddy进程，路径`E:/Program Files/WorkBuddy/WorkBuddy.exe`；进程存在不证明万得连接器已授权。
- 当前工具目录未提供WorkBuddy／Wind专用工具；插件检索`WorkBuddy`和`Wind 万得金融数据`分别返回空结果。
- PATH没有发现workbuddy／wind／codebuddy命令；当前环境未设置WORKBUDDY_ACCESS_TOKEN和WORKBUDDY_CLIENT_ID。没有读取客户端认证文件、Cookie、token或密钥。
- 安装包附带wb-guest-sdk脚本依赖应用内桥接，未发现可供此会话直接发送外部任务的已配置入口；未通过内部桥接、私有端口或凭据提取绕过授权。
- UI工具的启用表面没有原生应用，浏览器也未发现可用WorkBuddy页面；Chrome清单读取失败。未通过其他技术操作桌面UI。
- [官方Open API文档](https://open.workbuddy.cn/docs/openapi)提供GET本地助理状态和POST本地助理消息；需要第三方应用OAuth授权，消息调用使用user.localassistant.invokable权限。这里只发送一次无Authorization的GET状态请求，HTTP401。详见`workbuddy-openapi-probe.json`及对应原始95字节响应；没有POST、标签计算、拟合或SEALED读取。

后续最短路径：在WorkBuddy现有已授权万得连接器中执行`workbuddy-wind-smoke-test.md`。长期自动调用可采用官方第三方应用授权接口，需先建立合法客户端及对应权限；不能用桌面登录态自动视为本会话API授权。

测试范围固定600362.SH、2020-06-01至2020-06-05，最多一次RAW日线查询及一次字段／历史版本说明查询。要验证实际工具和原体可导出性、单位与版本能力；当前查询结果不能自动变为历史PIT资格。此文件仅补充证据，不改变ticket19任务状态或训练预算。
