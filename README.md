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

## Official fund-specific source locations (research)

Public page URLs located as possible fund-company PCF/NAV source entry points (not yet validated as parseable endpoints on GitHub runners):

| ETF | Source | URL |
| --- | --- | --- |
| 513650 | Southern Fund PCF query | https://www.southernfund.com/new/transaction-guide/detailed-list.html |
| 513870 | Fullgoal fund detail (includes '申赎清单' section) | https://www.fullgoal.com.cn/fundDetail/513870/index.html |
| 159612 | Guotai ETF PCF listing | https://e.gtfund.com/Etrade/Jijin/etflist |
| 159696 | E Fund official NAV/PCF | URL pending reliable identification |

The manual [Manager specific PCF source test](../../actions/workflows/manager-pcf-probe.yml) probes these links and the SSE PCF detail pages for 513650/513870. It saves only URL-access diagnostics and labeled HTML snippets as an Actions artifact. Many pages require JavaScript to populate detail, so absence of a fund code in static HTML is inconclusive.

No official IOPV endpoint, synchronized NAV, verified premium, or historical premium sample has been established by this test. We will not promote fund NAV to '14:00 fair value' without FX/index timing adjustments and source validation.

## Phase 3c — direct NAV labels from official manager websites

[Official NAV field validation](../../actions/workflows/official-nav-validation.yml) now checks:
- `513870`: Fullgoal fund-company **dated PCF previous-day NAV** and PCF announcement date.
- `159696`: E Fund's [official product page](https://www.efunds.com.cn/fund/159696_org.shtml), **dated reported unit NAV**.

The workflow is manual and **read-only**; it refuses missing labels, implausible values and future or >10-day-old NAV dates, and records explicitly that the values are **not** same-day 14:00 IOPV. Outputs are diagnostics for independent review, **not validated premiums**.

Other official sources and index/FX adjustment models are not yet validated. Do not compare an older NAV directly with current trading prices and call the result a live premium.

## Phase 3d — date-paired Sina SP500 NAV candidates (tested)

[Parse dated Sina S&P NAV](../../actions/workflows/parse-sina-nav.yml) completed a real runner test on 2026-10-22 and found:

| Code | Third-party unit NAV | NAV date | Validation |
| --- | --- | --- | --- |
| 513650 | 1.8673 CNY | 2026-10-20 | Correct fund code, near-top `单位净值` + `截止日期` fields, plausible |
| 159612 | 1.9235 CNY | 2026-10-20 | Same checks |

**Both remain third-party candidates, not official manager-verified NAVs.** Values are not contemporaneous with 2026-10-22 14:00 prices. No premium is computed, no record is written to `data/verified_1400.csv`, and the diagnostic artifact expires after 14 days.

Next: corroborate the dated NAV against manager PCF or a separate independently attributable source; determine an auditable reference-value model using market-session timestamps, index exposure and FX. Do not calculate percentiles from mixed premium definitions.

## Phase 4 — persisted, source-labeled historical NAV candidates

The [Collect dated NAV candidates](../../actions/workflows/collect-nav-candidates.yml) workflow is now configured for **16:05 and 22:05 China time on weekdays** (GitHub cron is best-effort; run timing is not guaranteed). It can also be triggered manually.

The initial actual GitHub Actions run on **2026-10-22 15:29 CST** successfully appended four records to [data/nav_candidates.csv](data/nav_candidates.csv):

| ETF | NAV date | NAV CNY | Source classification | Review status |
| --- | --- | ---: | --- | --- |
| 513870 | 2026-10-20 | 1.8803 | official fund manager webpage (Fullgoal) | manual field review required |
| 159696 | 2026-10-20 | 1.8384 | official fund manager webpage (E Fund) | manual field review required |
| 513650 | 2026-10-20 | 1.8673 | third-party Sina | not corroborated by fund manager |
| 159612 | 2026-10-20 | 1.9235 | third-party Sina | not corroborated by fund manager |

The collector records the **NAV date**, original source URL and classification, **first observed time**, PCF announcement date when available, and **candidate review status**. It deduplicates by date/fund/source and **fails closed on a changed same-date NAV** rather than silently overwriting history.

**Important:** these are reference NAV **candidates**, not real-time IOPV. They are independent of the four verified 14:00 *minute-labelled market price* observations; there is still no verified same-time fair value and therefore **no supported trading premium, historical premium percentile, or buy rating**. The "official manager page" classification means the data originated on the manager site, not that an independent human audit has occurred.

Automatic historical candidate collection is separately scheduled from the market-price collector. Neither writes to the other's CSV file.

## Phase 5 — cross-market data discovery and guarded pricing model (2026-10-22)

The [Cross market timestamp probe](../../actions/workflows/crossmarket-probe.yml) tested minute data availability for S&P 500 futures (`ES=F`), Nasdaq-100 futures (`NQ=F`), and USD/CNY (`CNY=X`) via Yahoo Chart (query1/query2). **All three failed with HTTP 429 (rate-limited)** on the GitHub runner. The probe was executed and diagnostics were saved; **no market values were obtained**. The 429 must not be treated as a valid data series or silently replaced by old reference quotes.

The [fair value guard tests](../../actions/workflows/test-fair-value-model.yml) exercise `scripts/fair_value_model.py`, a **pure, illustrative** implementation of:

`modeled_nav = dated_nav * index_now/index_at_NAV_valuation_cutoff * USD_CNY_now/USD_CNY_at_NAV_valuation_cutoff`

and `model_premium_percent = (market_price/modeled_nav - 1)*100`.

The tests passed on GitHub Actions, but **no live premiums have been calculated**. The model rejects different index instrument types between anchor and present (e.g. spot index versus futures), FX inverted currency orientation, stale or future timestamps, absent provenance and implausible prices. An actual NAV valuation cutoff must be documented per fund before selecting market anchors. **ES and NQ futures proxies are not interchangeable with total-return index data** and cannot by themselves guarantee an accurate ETF fair value because QDII accounting, tracking, fees and cash also matter.

Next priority: identify stable time-stamped FX and index data feeds which are accessible from GitHub, corroborate symbol units and actual NAV cutoff, then backtest modeled NAV versus subsequently published true NAV/IOPV. Price, NAV-candidate and source-diagnostic outputs remain separate, and no automated five-level investment rating has been enabled.

## Phase 6 — Sina FX and US index-futures snapshot candidates

On **2026-10-22 15:42 CST**, [China feeds index FX symbol probe](../../actions/workflows/china-crossmarket-probe.yml) obtained non-empty raw responses on Sina for:
- `USDCNY`: dated and clock-labeled US dollar / onshore RMB quote;
- `fx_susdcny` and `fx_susdcnh`: onshore/offshore RMB reference fields;
- `hf_ES`: labeled S&P 500 index future;
- `hf_NQ`: labeled Nasdaq index future.

The raw feeds returned dated clock labels; this demonstrates **reachability and schema candidates**, **not verified execution-grade futures price**, expiry, contract roll, official index reference, or 14:00 minute history. Sina `int_sp500` and `int_nasdaq` have no trustworthy quote timestamp in their short response; the latter is Nasdaq composite rather than guaranteed Nasdaq-100. Tencent lookup symbols in the research script are unverified alternatives.

A separate [Capture cross-market quote candidates](../../actions/workflows/capture-crossmarket.yml) is configured for approximately **14:03, 14:08, 14:13 China time on A-share trading days**. It records dated/clock-labeled **spot snapshots, not 14:00 minute price bars**, with source and field provenance, and rejects stale snapshots, missing labels, or wrong dates. Accepted snapshots, if any, will be stored at [data/crossmarket_quote_candidates.csv](data/crossmarket_quote_candidates.csv); its creation and content are pending the first successful capture run. [Offline parser tests](../../actions/workflows/test-crossmarket-capture.yml) passed on GitHub Actions.

This supplementary dataset **must not be inserted into NAV or formal ETF premium calculations yet**. We still lack matched historical anchor timestamps corresponding to each NAV valuation cutoff, and independent checks of futures instrument specification/contract rolls. With only current snapshot futures or FX, a correct cross-market fair-value estimate remains unavailable.

The previous Yahoo Finance endpoint returned HTTP 429 for all three desired series. We do not retry it in the scheduled candidate capture.
