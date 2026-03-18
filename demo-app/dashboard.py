from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None

    ordered = sorted(values)
    index = math.ceil((percentile / 100) * len(ordered)) - 1
    return ordered[max(index, 0)]


@dataclass
class EndpointMetrics:
    requests: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0
    durations_ms: list[float] = field(default_factory=list)
    last_duration_ms: float | None = None
    cache_hits: int = 0
    cache_misses: int = 0

    def record(self, duration_ms: float, success: bool, cache_status: str | None = None) -> None:
        self.requests += 1
        self.total_duration_ms += duration_ms
        self.durations_ms.append(duration_ms)
        self.last_duration_ms = duration_ms

        if success:
            self.successes += 1
        else:
            self.failures += 1

        if cache_status == "hit":
            self.cache_hits += 1
        elif cache_status == "miss":
            self.cache_misses += 1

    def snapshot(self) -> dict[str, Any]:
        avg_ms = self.total_duration_ms / self.requests if self.requests else None
        p95_ms = _percentile(self.durations_ms, 95)
        failure_rate = self.failures / self.requests if self.requests else None
        hit_ratio = self.cache_hits / max(self.cache_hits + self.cache_misses, 1) if self.cache_hits or self.cache_misses else None

        return {
            "requests": self.requests,
            "successes": self.successes,
            "failures": self.failures,
            "avg_ms": round(avg_ms, 2) if avg_ms is not None else None,
            "p95_ms": round(p95_ms, 2) if p95_ms is not None else None,
            "last_ms": round(self.last_duration_ms, 2) if self.last_duration_ms is not None else None,
            "failure_rate": round(failure_rate, 4) if failure_rate is not None else None,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_ratio": round(hit_ratio, 4) if hit_ratio is not None else None,
        }


class DemoMetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ranking_direct = EndpointMetrics()
        self._ranking_cache = EndpointMetrics()

    def record_ranking_direct(self, duration_ms: float, success: bool) -> None:
        with self._lock:
            self._ranking_direct.record(duration_ms=duration_ms, success=success)

    def record_ranking_cache(self, duration_ms: float, success: bool, cache_status: str | None = None) -> None:
        with self._lock:
            self._ranking_cache.record(duration_ms=duration_ms, success=success, cache_status=cache_status)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ranking_direct": self._ranking_direct.snapshot(),
                "ranking_cache": self._ranking_cache.snapshot(),
            }


def load_latest_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "invalid",
            "message": f"invalid JSON in {path}",
            "generated_at": None,
        }


def normalize_latest_report(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if report is None:
        return None

    if report.get("status") == "invalid":
        return report

    endpoints = report.get("endpoints") or {}
    ranking_direct = endpoints.get("ranking_direct")
    ranking_cache = endpoints.get("ranking_cache")

    if not ranking_direct or not ranking_cache:
        return {
            "status": "stale",
            "generated_at": report.get("generated_at"),
            "message": "현재 요약 파일은 이전 db-direct/cache 시나리오 결과입니다. ranking 시나리오로 k6를 다시 실행하세요.",
        }

    return {
        "status": "ready",
        **report,
    }


def build_dashboard_payload(
    metrics_store: DemoMetricsStore,
    report_path: Path,
    ranking_preview: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": {
            "title": "Fashion Ranking Cache Demo",
            "ranking_name": ranking_preview["ranking_name"],
            "catalog_size": ranking_preview["catalog_size"],
            "top_n": 10,
            "ttl_seconds": 5,
            "load_profile": "100 VUs x 10s",
            "cache_key": "ranking:top10",
            "algorithm": "views + likes + wishlists + sales + reviews + repeat buyers + freshness",
        },
        "ranking_preview": ranking_preview,
        "live_metrics": metrics_store.snapshot(),
        "latest_report": normalize_latest_report(load_latest_report(report_path)),
        "report_path": str(report_path),
    }


def build_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Minimi Ranking Cache Demo</title>
    <style>
      :root {
        --bg: #f7f1e7;
        --paper: rgba(255, 250, 243, 0.92);
        --ink: #1f2430;
        --muted: #5d6777;
        --accent: #d95d39;
        --accent-soft: rgba(217, 93, 57, 0.14);
        --cache: #1b7f6a;
        --cache-soft: rgba(27, 127, 106, 0.14);
        --line: rgba(31, 36, 48, 0.12);
        --shadow: 0 20px 50px rgba(58, 45, 31, 0.12);
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        font-family: "Avenir Next", "Pretendard", "Apple SD Gothic Neo", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(217, 93, 57, 0.15), transparent 30%),
          radial-gradient(circle at top right, rgba(27, 127, 106, 0.12), transparent 26%),
          linear-gradient(180deg, #f9f4ea 0%, #f2eadf 100%);
      }

      main {
        width: min(1240px, calc(100vw - 32px));
        margin: 24px auto 48px;
      }

      .hero,
      .panel {
        background: var(--paper);
        border: 1px solid rgba(31, 36, 48, 0.08);
        box-shadow: var(--shadow);
      }

      .hero {
        border-radius: 28px;
        padding: 28px;
      }

      .eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.72);
        color: var(--muted);
        font-size: 13px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }

      h1 {
        margin: 16px 0 8px;
        font-size: clamp(30px, 5vw, 58px);
        line-height: 0.96;
        letter-spacing: -0.04em;
      }

      .lede {
        margin: 0;
        max-width: 760px;
        color: var(--muted);
        font-size: 18px;
        line-height: 1.6;
      }

      .chip-row,
      .button-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      .chip-row {
        margin-top: 20px;
      }

      .chip {
        padding: 10px 14px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid rgba(31, 36, 48, 0.08);
        font-size: 14px;
      }

      .cta-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 22px;
      }

      .cta,
      button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 999px;
        padding: 12px 16px;
        font: inherit;
        cursor: pointer;
        color: white;
        text-decoration: none;
        background: linear-gradient(135deg, #172033, #33405b);
      }

      .cta.alt,
      button.alt {
        background: linear-gradient(135deg, #1b7f6a, #39b89b);
      }

      button.warn {
        background: linear-gradient(135deg, #b0472d, #d95d39);
      }

      .grid {
        display: grid;
        grid-template-columns: repeat(12, minmax(0, 1fr));
        gap: 18px;
        margin-top: 18px;
      }

      .panel {
        border-radius: 24px;
        padding: 22px;
      }

      .panel h2 {
        margin: 0 0 10px;
        font-size: 20px;
        letter-spacing: -0.03em;
      }

      .panel p {
        margin: 0;
        color: var(--muted);
        line-height: 1.6;
      }

      .wide {
        grid-column: span 7;
      }

      .narrow {
        grid-column: span 5;
      }

      .full {
        grid-column: 1 / -1;
      }

      .metric-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
        margin-top: 18px;
      }

      .metric-card {
        border-radius: 18px;
        padding: 18px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.7);
      }

      .metric-card.db {
        background: linear-gradient(180deg, rgba(217, 93, 57, 0.08), rgba(255, 255, 255, 0.72));
      }

      .metric-card.cache {
        background: linear-gradient(180deg, rgba(27, 127, 106, 0.08), rgba(255, 255, 255, 0.72));
      }

      .metric-title,
      .bar-label {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        color: var(--muted);
        font-size: 14px;
      }

      .metric-title {
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 13px;
      }

      .metric-value {
        margin-top: 10px;
        font-size: 34px;
        font-weight: 700;
        letter-spacing: -0.04em;
      }

      .metric-sub {
        margin-top: 8px;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.6;
      }

      .preview-list {
        margin: 18px 0 0;
        padding: 0;
        list-style: none;
        display: grid;
        gap: 10px;
      }

      .preview-item {
        display: grid;
        grid-template-columns: 60px 1fr auto;
        gap: 14px;
        align-items: center;
        padding: 12px 14px;
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid var(--line);
      }

      .rank-pill {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        width: 60px;
        height: 44px;
        border-radius: 14px;
        background: linear-gradient(135deg, #172033, #33405b);
        color: white;
        font-weight: 700;
      }

      .preview-name {
        font-weight: 700;
      }

      .preview-meta {
        margin-top: 4px;
        color: var(--muted);
        font-size: 14px;
      }

      .score {
        font-size: 18px;
        font-weight: 700;
      }

      .flow {
        display: grid;
        gap: 10px;
        margin-top: 18px;
      }

      .flow-step,
      .empty,
      pre {
        border-radius: 18px;
      }

      .flow-step {
        padding: 14px 16px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.68);
      }

      .kicker {
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }

      .bars {
        margin-top: 16px;
        display: grid;
        gap: 12px;
      }

      .bar-row {
        display: grid;
        gap: 8px;
      }

      .bar-track {
        height: 12px;
        border-radius: 999px;
        background: rgba(31, 36, 48, 0.08);
        overflow: hidden;
      }

      .bar-fill {
        height: 100%;
        border-radius: 999px;
      }

      .bar-fill.db {
        background: linear-gradient(90deg, #d95d39, #ef8d4f);
      }

      .bar-fill.cache {
        background: linear-gradient(90deg, #1b7f6a, #39b89b);
      }

      .empty {
        margin-top: 18px;
        padding: 16px;
        background: rgba(255, 255, 255, 0.68);
        border: 1px dashed rgba(31, 36, 48, 0.16);
        color: var(--muted);
        line-height: 1.6;
      }

      .playground {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 18px;
        margin-top: 18px;
      }

      .field-group {
        display: grid;
        gap: 12px;
      }

      .field-group label {
        display: grid;
        gap: 8px;
        color: var(--muted);
        font-size: 14px;
      }

      input,
      textarea {
        width: 100%;
        border: 1px solid rgba(31, 36, 48, 0.14);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.74);
        padding: 14px 16px;
        color: var(--ink);
        font: inherit;
      }

      textarea {
        min-height: 220px;
        resize: vertical;
      }

      pre {
        margin: 0;
        padding: 16px;
        min-height: 320px;
        background: #182033;
        color: #edf2ff;
        overflow: auto;
        white-space: pre-wrap;
        word-break: break-word;
      }

      .footnote {
        margin-top: 16px;
        color: var(--muted);
        font-size: 13px;
      }

      @media (max-width: 900px) {
        .wide,
        .narrow,
        .full {
          grid-column: 1 / -1;
        }

        .metric-grid {
          grid-template-columns: 1fr;
        }

        .playground {
          grid-template-columns: 1fr;
        }

        .preview-item {
          grid-template-columns: 52px 1fr;
        }

        .score {
          grid-column: 2;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="eyebrow">Minimi Demo App</div>
        <h1>랭킹 계산이 비쌀수록, 캐시 유무가 더 크게 드러납니다</h1>
        <p class="lede">
          이 화면은 1000개 상품 후보를 읽고 점수를 계산해 상위 10을 뽑는 랭킹 시나리오를 보여줍니다.
          demo-app 실시간 메트릭과 마지막 k6 결과를 같은 화면에서 비교할 수 있습니다.
        </p>
        <div id="scenario-chips" class="chip-row"></div>
        <div class="cta-row">
          <a class="cta" href="/ranking-direct" target="_blank" rel="noreferrer">/ranking-direct 보기</a>
          <a class="cta alt" href="/ranking-cache" target="_blank" rel="noreferrer">/ranking-cache 보기</a>
        </div>
      </section>

      <section class="grid">
        <article class="panel wide">
          <h2>실시간 요청 메트릭</h2>
          <p>브라우저는 2초마다 데이터를 다시 불러옵니다. 페이지를 새로고침하지 않아도 k6 결과와 live metric이 갱신됩니다.</p>
          <div id="live-metrics" class="metric-grid"></div>
        </article>

        <article class="panel narrow">
          <h2>랭킹 Top Preview</h2>
          <p>미리 계산한 상위 후보 5개입니다. 실제 API는 top 10을 반환합니다.</p>
          <ul id="ranking-preview" class="preview-list"></ul>
        </article>

        <article class="panel full">
          <h2>요청 흐름</h2>
          <p>같은 랭킹 연산을 direct와 cache 두 경로로 비교합니다.</p>
          <div class="flow">
            <div class="flow-step">
              <div class="kicker">Ranking Direct</div>
              상품 1000개를 읽고 조회수, 좋아요, 위시리스트, 판매량, 리뷰, 재구매 지표를 합산해 상위 10을 매번 다시 계산합니다.
            </div>
            <div class="flow-step">
              <div class="kicker">Ranking Cache</div>
              먼저 <code>ranking:top10</code> 을 읽고, miss일 때만 같은 계산을 수행한 뒤 TTL 5초로 저장합니다.
            </div>
            <div class="flow-step">
              <div class="kicker">Why It Matters</div>
              비싼 집계와 정렬이 많은 조회일수록 캐시 hit의 이득이 더 커지고, 같은 시간에 더 많은 요청을 처리할 수 있습니다.
            </div>
          </div>
        </article>

        <article class="panel full">
          <h2>마지막 k6 실행 결과</h2>
          <p>k6가 저장한 JSON 요약 파일을 demo-app이 읽어 시각화합니다.</p>
          <div id="latest-report"></div>
        </article>

        <article class="panel full">
          <h2>MiniRedis Playground</h2>
          <p>랭킹 캐시와 별개로 저장, 조회, 삭제를 직접 시연할 수 있습니다.</p>
          <div class="playground">
            <div class="field-group">
              <label>
                Key
                <input id="store-key" type="text" value="demo:manual:ranking" />
              </label>
              <label>
                TTL Seconds
                <input id="store-ttl" type="number" min="0" value="30" />
              </label>
              <label>
                JSON Value
                <textarea id="store-value">{
  "feature": "manual demo",
  "scenario": "fashion ranking",
  "catalog_size": 1000,
  "top_n": 10
}</textarea>
              </label>
              <div class="button-row">
                <button id="save-button" type="button">Save</button>
                <button id="get-button" type="button" class="alt">Get</button>
                <button id="delete-button" type="button" class="warn">Delete</button>
              </div>
            </div>
            <pre id="playground-output">playground result will appear here</pre>
          </div>
          <p class="footnote">결과 파일 경로: <span id="report-path"></span></p>
        </article>
      </section>
    </main>

    <script>
      const scenarioChips = document.getElementById('scenario-chips');
      const previewList = document.getElementById('ranking-preview');
      const liveMetrics = document.getElementById('live-metrics');
      const latestReport = document.getElementById('latest-report');
      const reportPath = document.getElementById('report-path');
      const storeKeyInput = document.getElementById('store-key');
      const storeTtlInput = document.getElementById('store-ttl');
      const storeValueInput = document.getElementById('store-value');
      const playgroundOutput = document.getElementById('playground-output');

      function formatMs(value) {
        if (value === null || value === undefined) {
          return '-';
        }
        return `${Number(value).toFixed(2)} ms`;
      }

      function formatPercent(value, digits = 2) {
        if (value === null || value === undefined) {
          return '-';
        }
        return `${Number(value).toFixed(digits)}%`;
      }

      function formatInteger(value) {
        return new Intl.NumberFormat('ko-KR').format(value || 0);
      }

      function escapeHtml(value) {
        return String(value)
          .replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;')
          .replaceAll('>', '&gt;')
          .replaceAll('"', '&quot;')
          .replaceAll("'", '&#39;');
      }

      function metricCard(title, theme, metric, description) {
        const hasCacheStats = (metric.cache_hits || 0) + (metric.cache_misses || 0) > 0;
        const cacheLine = hasCacheStats
          ? `hit ${formatInteger(metric.cache_hits)} / miss ${formatInteger(metric.cache_misses)} / hit ratio ${formatPercent((metric.hit_ratio || 0) * 100)}`
          : 'cache bypass path';

        return `
          <article class="metric-card ${theme}">
            <div class="metric-title">
              <span>${title}</span>
              <span>${formatInteger(metric.requests)} req</span>
            </div>
            <div class="metric-value">${formatMs(metric.avg_ms)}</div>
            <div class="metric-sub">
              p95 ${formatMs(metric.p95_ms)} · last ${formatMs(metric.last_ms)} · fail ${formatPercent((metric.failure_rate || 0) * 100)}<br />
              ${escapeHtml(description)}<br />
              ${escapeHtml(cacheLine)}
            </div>
          </article>
        `;
      }

      function renderScenario(data) {
        const scenario = data.scenario;
        const chips = [
          scenario.title,
          `${formatInteger(scenario.catalog_size)} candidates`,
          `Top ${scenario.top_n}`,
          `TTL ${scenario.ttl_seconds}s`,
          scenario.load_profile,
          scenario.cache_key,
        ];

        scenarioChips.innerHTML = chips
          .map((value) => `<div class="chip">${escapeHtml(value)}</div>`)
          .join('');

        reportPath.textContent = data.report_path;
      }

      function renderPreview(preview) {
        previewList.innerHTML = preview.top_products
          .map((product) => `
            <li class="preview-item">
              <div class="rank-pill">#${product.rank}</div>
              <div>
                <div class="preview-name">${escapeHtml(product.name)}</div>
                <div class="preview-meta">
                  ${escapeHtml(product.brand)} · ${escapeHtml(product.category)} · 판매 ${formatInteger(product.sales_28d)} · 좋아요 ${formatInteger(product.likes_28d)}
                </div>
              </div>
              <div class="score">${product.score.toFixed(2)}</div>
            </li>
          `)
          .join('');
      }

      function renderLiveMetrics(metrics) {
        liveMetrics.innerHTML = [
          metricCard('Ranking Direct', 'db', metrics.ranking_direct, '매 요청마다 1000개 후보를 다시 계산합니다.'),
          metricCard('Ranking Cache', 'cache', metrics.ranking_cache, 'ranking:top10 캐시를 먼저 읽고, miss일 때만 다시 계산합니다.'),
        ].join('');
      }

      function compareBars(label, directValue, cacheValue, suffix, higherIsBetter = false) {
        const base = Math.max(directValue || 0, cacheValue || 0, 1);
        const directWidth = `${((directValue || 0) / base) * 100}%`;
        const cacheWidth = `${((cacheValue || 0) / base) * 100}%`;
        const note = higherIsBetter
          ? `Direct ${directValue}${suffix} / Cache ${cacheValue}${suffix}`
          : `Direct ${directValue}${suffix} / Cache ${cacheValue}${suffix}`;

        return `
          <div class="bar-row">
            <div class="bar-label">
              <span>${label}</span>
              <span>${note}</span>
            </div>
            <div class="bar-track"><div class="bar-fill db" style="width:${directWidth}"></div></div>
            <div class="bar-track"><div class="bar-fill cache" style="width:${cacheWidth}"></div></div>
          </div>
        `;
      }

      function reportSummaryCard(label, tone, endpoint) {
        return `
          <article class="metric-card ${tone}">
            <div class="metric-title">
              <span>${label}</span>
              <span>${formatInteger(endpoint.request_count)} req</span>
            </div>
            <div class="metric-value">${formatMs(endpoint.avg_ms)}</div>
            <div class="metric-sub">
              p95 ${formatMs(endpoint.p95_ms)} · fail ${formatPercent(endpoint.fail_rate * 100)}<br />
              ${Number(endpoint.rps).toFixed(2)} RPS
            </div>
          </article>
        `;
      }

      function renderLatestReport(report) {
        if (!report) {
          latestReport.innerHTML = '<div class="empty">아직 k6 요약 파일이 없습니다. <code>k6 run k6/basic.js</code> 를 실행하면 이 영역이 채워집니다.</div>';
          return;
        }

        if (report.status === 'invalid' || report.status === 'stale') {
          latestReport.innerHTML = `<div class="empty">${escapeHtml(report.message || '요약 파일을 읽지 못했습니다.')}</div>`;
          return;
        }

        const direct = report.endpoints.ranking_direct;
        const cache = report.endpoints.ranking_cache;
        const comparison = report.comparison;

        latestReport.innerHTML = `
          <div class="metric-grid">
            ${reportSummaryCard('K6 Ranking Direct', 'db', direct)}
            ${reportSummaryCard('K6 Ranking Cache', 'cache', cache)}
          </div>
          <div class="bars">
            ${compareBars('Average latency', direct.avg_ms, cache.avg_ms, ' ms')}
            ${compareBars('p95 latency', direct.p95_ms, cache.p95_ms, ' ms')}
            ${compareBars('RPS', direct.rps, cache.rps, '', true)}
          </div>
          <div class="empty">
            평균 응답시간 개선: <strong>${formatPercent(comparison.avg_latency_improvement_pct)}</strong><br />
            p95 개선: <strong>${formatPercent(comparison.p95_latency_improvement_pct)}</strong><br />
            처리량 증가: <strong>${formatPercent(comparison.rps_gain_pct)}</strong><br />
            마지막 요약 시각: <strong>${escapeHtml(report.generated_at || '-')}</strong>
          </div>
        `;
      }

      async function refreshDashboard() {
        const response = await fetch('/dashboard-data');
        const payload = await response.json();

        renderScenario(payload);
        renderPreview(payload.ranking_preview);
        renderLiveMetrics(payload.live_metrics);
        renderLatestReport(payload.latest_report);
      }

      async function callPlayground(method) {
        const key = storeKeyInput.value.trim();
        if (!key) {
          playgroundOutput.textContent = 'key is required';
          return;
        }

        let response;
        if (method === 'POST') {
          let parsedValue;
          try {
            parsedValue = JSON.parse(storeValueInput.value);
          } catch (error) {
            playgroundOutput.textContent = `invalid JSON: ${error.message}`;
            return;
          }

          response = await fetch('/demo-store', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              key,
              value: parsedValue,
              ttl_seconds: storeTtlInput.value ? Number(storeTtlInput.value) : null,
            }),
          });
        } else {
          const url = `/demo-store?key=${encodeURIComponent(key)}`;
          response = await fetch(url, { method });
        }

        const payload = await response.json();
        playgroundOutput.textContent = JSON.stringify(payload, null, 2);
      }

      document.getElementById('save-button').addEventListener('click', () => callPlayground('POST'));
      document.getElementById('get-button').addEventListener('click', () => callPlayground('GET'));
      document.getElementById('delete-button').addEventListener('click', () => callPlayground('DELETE'));

      refreshDashboard().catch((error) => {
        latestReport.innerHTML = `<div class="empty">dashboard-data를 읽지 못했습니다: ${escapeHtml(error.message)}</div>`;
      });
      window.setInterval(() => {
        refreshDashboard().catch((error) => {
          latestReport.innerHTML = `<div class="empty">dashboard-data를 읽지 못했습니다: ${escapeHtml(error.message)}</div>`;
        });
      }, 2000);
    </script>
  </body>
</html>
"""
