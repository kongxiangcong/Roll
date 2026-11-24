import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("盘后同步、记账、冻结导出和双组合回测", async ({ page }) => {
  const day = "2025-08-01";
  const initialRequests: string[] = [];
  page.on("request", (r) => initialRequests.push(new URL(r.url()).pathname));
  await page.goto("/?day=" + day);
  await expect(page.getByRole("heading", { name: "四维得分" })).toBeVisible();
  expect(initialRequests).not.toContain("/api/account");
  await page.getByLabel("数据范围").selectOption("daily");
  await page.getByLabel("起始日（留空增量）").fill("2025-07-28");
  await page.getByRole("button", { name: "同步数据", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "同步完成" }),
  ).toBeVisible({ timeout: 120000 });
  await page.getByRole("link", { name: "持仓与跟踪池" }).click();
  await page.getByLabel("初始现金（元）").fill("0");
  await page.getByLabel("凭据来源").fill("测试账本");
  await page.getByRole("button", { name: "预览记账" }).click();
  await page.getByRole("button", { name: "确认入账" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "已确认入账" }),
  ).toContainText("版本 1");
  await page.getByLabel("金额（元）").fill("5000");
  await page.getByLabel("凭据来源").fill("隔离转入记录");
  await page.getByRole("button", { name: "预览记账" }).click();
  await page.getByRole("button", { name: "确认入账" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "已确认入账" }),
  ).toContainText("5,000");
  await page.getByLabel("记录类型").selectOption("FILL");
  await page.getByLabel("证券代码").fill("600362.SH");
  await page.getByLabel("成交数量（股）").fill("100");
  await page.getByLabel("成交价格（元）").fill("20");
  await page.getByLabel("实际费用（元）").fill("5");
  await page.getByLabel("凭据来源").fill("隔离交割单");
  await page.getByRole("button", { name: "预览记账" }).click();
  await page.getByRole("button", { name: "确认入账" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "已确认入账" }),
  ).toContainText("2,995");
  await expect(page.getByText("YAML 配置 · 只读")).toBeVisible();
  await page.getByRole("link", { name: "今日晴雨表" }).click();
  await page.getByRole("button", { name: "冻结日报" }).click();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载 JSON" }).click();
  const file = await downloaded;
  const report = JSON.parse(await readFile((await file.path())!, "utf8"));
  expect(report.account.cash_balance).toBe("2995.00");
  expect(report.account.positions[0].quantity).toBe("100");
  await page.reload();
  await page.getByRole("button", { name: "重读日报" }).click();
  await expect(page.getByText(/^冻结截止/)).toContainText(
    report.cutoff_at.slice(0, 10),
  );
  await page.getByRole("link", { name: "回测与校准", exact: true }).click();
  await page.getByLabel("回测起始日").fill("2025-07-30");
  await page.getByRole("button", { name: "运行回测与校准" }).click();
  await expect(
    page.getByRole("heading", { name: "实际冻结的前向预测" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "样本外 · 扣费净值" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
