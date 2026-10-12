# 28首个垂直切片

基于独立接受77f729f，FastAPI公共入口/真实SQLite、API角色、ROLL_ENV=test；未外发/真实授权。

红灯：test_notifications.py首个test在GET /api/notifications得到404，1 failed in9.34s，exit1，准确隔离目录backend/.test-tmp-notifications-01。

绿灯：同test新增最小站内列表/current/read、同事务permission-event消费者，1 passed in5.09s，exit0，backend/.test-tmp-notifications-02。验证重复pause命令不重复通知、显式read幂等及重启保留、delivery未知，GET不推定read。

不是28整票/外部交付结项；后续实际日志与源绑定记录另存。
