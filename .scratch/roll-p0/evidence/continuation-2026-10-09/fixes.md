# 双轴评审修正

已先合入集成 `adefd25`，由同一实施分支修正 Spec 与 Standards 两项P2。

## Spec：零成交量/正成交额冲突

新增FastAPI+真实SQLite+隔离归档回归，注入SOHU `volume=0`、`amount=10`万元。修正前精确红：`errors=[]`，预期 `ZERO_VOLUME_POSITIVE_AMOUNT_CONFLICT`，1 failed，5.22秒。修正后保留原报告0股、100000元和ZERO_REPORTED，同时errors包含冲突、quality=INVALID、model_daily_input_allowed=false，宿主产生DATA_QUALITY_ALERT。原始材料不改写，也不推断停牌。11项SOHU回归全部通过，28.19秒；原0量/0额报告仍保留零报告语义。

## Standards：真实验收脚本拥有本次HTTP运行

根集成 `adefd25` 已采用内核分配空闲端口、显式占用预检、每次启动/重启的随机身份token和数据目录比对、子进程存活检查；本次复核补齐身份返回pid必须等于当前Popen.pid，以及start()内部任意启动异常的自身子进程terminate/wait清理。因为外部 `process=start()` 尚未赋值时finally拿不到已启动实例，这项清理须在start()自身执行。只终止本次创建的实例，不访问或终止已有服务。

真实CLI验证：本机socket占用55914后运行 helper --port55914，实际exit1、WinError10048，未创建SQLite、http-process.log=0字节，因此未生成子进程或市场/账户写入。检查结果保存在实施树 `.scratch/sohu-occupied-port/verification.json`。完整成功启动/token+directory+pid及重启真实v3由集成树统一运行，不以此占用端口检查冒充真实供应商或成功身份路径证据。

修改仅一处生产SOHU质量校验、一项公开API回归、实际验收辅助脚本的启动身份/自身异常清理与此记录。无新依赖、资格放宽、封存读取、真实账户写入或全后端重复测试。
