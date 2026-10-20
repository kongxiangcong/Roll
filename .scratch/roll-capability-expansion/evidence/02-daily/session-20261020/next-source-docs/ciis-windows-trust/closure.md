# Windows 信任库单次核查封口

plan.json在请求前冻结。curl8.21 Schannel使用Windows受信任证书库，保持TLS校验，无重试或重定向。实际仅一次请求，16.5104秒，HTTP000/0响应字节、exit60 SEC_E_UNTRUSTED_ROOT；receipt.json和01-result.log保存原始错误。日志ssl_verify=0不是成功证据，exit60表示证书校验失败。

未取得服务器响应正文，因此没有01.raw；不存在可可信读取的样本链接。其余3次请求封口，不降级HTTP、不关闭验证、不猜测URL。此失败不能证明需要登录/凭证/付费，也不能证明匿名样本不存在。
