# QDII ETF Premium Tracker

四只 A 股场内 QDII ETF 的公开行情采集项目（**测试阶段**）。

| 指数 | 主选 | 备选 |
|---|---|---|
| 标普500 | 513650.SH 南方 | 159612.SZ 国泰 |
| 纳斯达克100 | 513870.SH 富国 | 159696.SZ 易方达 |

## 当前阶段：仅测试网络和分钟行情

进入 **Actions → ETF quote connectivity test → Run workflow** 手动运行。程序检测新浪公开行情接口和腾讯四只 ETF 分钟行情接口，记录 JSON 诊断报告。报告可以在 Actions 运行记录页面的 Artifacts 下载，也可以在日志查看。

**当前没有开启每日自动定时**，没有建立正式价格历史库，也不会计算或保存未经核验的溢价。

仅在北京时间 14:02—14:30，且腾讯返回交易日期为当天、含 `1400` 标记和有效价格时，记录状态 `candidate_minute_bar`。`1400` 表示腾讯的**分钟标记**，不是交易所精确到秒的逐笔时间戳；`candidate_minute_bar` 也不等于最终有效样本。

**GitHub Actions 运行成功（绿色）不代表行情抓取成功。** 需要检查 JSON 每只基金的 `status` 和原始交易日期。即使测试通过，仍需要核实字段含义、交易所休市日、停牌、IOPV/NAV 日期、汇率和指数期货后才能正式安排每日采集。

使用的公开网页接口不保证稳定性，也不属于具有服务承诺的官方开发 API。公开仓库不保存任何密钥。

本项目仅供技术研究与信息参考，不构成投资建议。


## Phase 2 — automatic dated 14:00 minute observations

Workflow: [ETF 14:00 minute capture](../../actions/workflows/capture-1400.yml).

- Runs on weekdays at 14:03, 14:08 and 14:13 **Asia/Shanghai** (UTC cron 06:03, 06:08 and 06:13), and supports manual triggering.
- Uses the **Shanghai exchange calendar** to skip known A-share holidays and weekends. If the calendar is unavailable, collection fails closed.
- Reads the Tencent **14:00-labelled minute** row for each ETF; independently validates `date=YYYYMMDD`, 13:59 and 14:00 rows, plausible price and **increasing cumulative volume**.
- Probes the Sina quote feed but does **not** interpret a later snapshot as the 14:00 price.
- Writes only accepted **minute observations**, deduplicated by (trade_date, code, minute), to [data/verified_1400.csv](data/verified_1400.csv). The price is **not** an exchange tick at exactly 14:00:00.
- Persists diagnostics as a temporary Actions artifact and logs; a successful workflow does not prove all four symbols were accepted.
- Scheduled runs can be delayed or skipped by GitHub. If execution misses the 14:02–14:45 verification window, **no data are written**.
- No IOPV, NAV, index futures, FX estimate, historical premium percentile, or buy grade is produced. Such fields must be separately sourced and validated before publication.

Security: this workflow requests `contents: write` solely to append the validated CSV to its own repository. No API credentials or third-party integrations are stored.

## Phase 3 — IOPV / NAV source feasibility test

[ETF IOPV and NAV source probe](../../actions/workflows/reference-value-probe.yml) is a **manual, read-only** diagnostic. It tests Tencent quotation fields and an unauthenticated Eastmoney fund estimate endpoint. The diagnostic result is a temporary artifact `reference-value-source-diagnostic`.

**No returned field is treated as verified IOPV.** The publicly accessible fund estimation endpoint may be unavailable or unsupported for cross-border ETFs, and an estimated fund value is not equivalent to the exchange-published IOPV. Neither the previous NAV nor a quote snapshot is sufficient to compute contemporaneous 14:00 ETF premiums.

Next: locate the relevant fund/official IOPV provider, verify quote unit, timestamp, trading session and underlying FX/index handling; then develop separate synchronized premium calculations without altering the validated price CSV.

## Phase 3b — official exchange / manager source exploration

[Official IOPV and PCF page probe](../../actions/workflows/official-source-probe.yml) is a manual, read-only GitHub Actions test for the Shanghai Stock Exchange ETF pages, SSE/SZSE home pages and Southern Fund PCF page. It records page reachability and textual indicators **only**, with no inferred or unverified IOPV, no premium, and no changes to `data/verified_1400.csv`.

SSE publishes ETF PCF information and whether IOPV disclosure is required; the PCF NAV date may be T-2 for cross-border ETFs. The SSE's IOPV source-upload interface is for approved institutions and is not an unrestricted retail data API. The next task is to identify a lawful, stable, timestamped **published** IOPV feed for each instrument, not to confuse uploading IOPV to the exchange with downloading the public reference price.
