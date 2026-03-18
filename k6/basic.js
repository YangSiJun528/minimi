import http from 'k6/http';
import { check } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.DEMO_APP_BASE_URL || 'http://localhost:8001';
const SUMMARY_PATH = __ENV.K6_SUMMARY_PATH || 'demo-app/perf-results/latest.json';
const RANKING_DIRECT_URL = `${BASE_URL}/ranking-direct`;
const RANKING_CACHE_URL = `${BASE_URL}/ranking-cache`;
const TEST_PROFILE = {
  title: 'Fashion Ranking Cache Demo',
  catalog_size: 1000,
  top_n: 10,
  viewers: 100,
  duration_seconds: 10,
  ttl_seconds: 5,
  cache_key: 'ranking:top10',
};

const rankingDirectDuration = new Trend('ranking_direct_duration');
const rankingCacheDuration = new Trend('ranking_cache_duration');
const rankingDirectRequests = new Counter('ranking_direct_requests');
const rankingCacheRequests = new Counter('ranking_cache_requests');
const rankingDirectFailures = new Rate('ranking_direct_failures');
const rankingCacheFailures = new Rate('ranking_cache_failures');

export const options = {
  scenarios: {
    ranking_cache: {
      executor: 'constant-vus',
      exec: 'hitRankingCache',
      vus: 100,
      duration: '10s',
      gracefulStop: '0s',
    },
    ranking_direct: {
      executor: 'constant-vus',
      exec: 'hitRankingDirect',
      vus: 100,
      duration: '10s',
      startTime: '12s',
      gracefulStop: '0s',
    },
  },
  thresholds: {
    ranking_direct_failures: ['rate<0.01'],
    ranking_cache_failures: ['rate<0.01'],
  },
};

function recordResult(response, requestCounter, durationTrend, failureRate, label) {
  requestCounter.add(1);
  durationTrend.add(response.timings.duration);
  failureRate.add(response.status !== 200);

  check(response, {
    [`${label} returned 200`]: (res) => res.status === 200,
  });
}

export function setup() {
  http.get(RANKING_CACHE_URL, {
    tags: { endpoint: 'ranking-cache-warmup' },
  });
}

export function hitRankingDirect() {
  const response = http.get(RANKING_DIRECT_URL, {
    tags: { endpoint: 'ranking-direct' },
  });
  recordResult(
    response,
    rankingDirectRequests,
    rankingDirectDuration,
    rankingDirectFailures,
    'ranking-direct',
  );
}

export function hitRankingCache() {
  const response = http.get(RANKING_CACHE_URL, {
    tags: { endpoint: 'ranking-cache' },
  });
  recordResult(
    response,
    rankingCacheRequests,
    rankingCacheDuration,
    rankingCacheFailures,
    'ranking-cache',
  );
}

function readTrend(metric) {
  return {
    avg_ms: Number((metric?.values?.avg ?? 0).toFixed(2)),
    p95_ms: Number((metric?.values?.['p(95)'] ?? 0).toFixed(2)),
  };
}

function readCounter(metric) {
  return {
    request_count: Number((metric?.values?.count ?? 0).toFixed(0)),
    rps: Number((metric?.values?.rate ?? 0).toFixed(2)),
  };
}

function readRate(metric) {
  return Number((metric?.values?.rate ?? 0).toFixed(4));
}

function endpointSummary(label, url, durationMetric, requestMetric, failureMetric) {
  return {
    label,
    url,
    ...readTrend(durationMetric),
    ...readCounter(requestMetric),
    fail_rate: readRate(failureMetric),
  };
}

function improvement(directValue, cacheValue) {
  if (!directValue) {
    return 0;
  }

  return Number((((directValue - cacheValue) / directValue) * 100).toFixed(2));
}

function gain(cacheValue, directValue) {
  if (!directValue) {
    return 0;
  }

  return Number((((cacheValue - directValue) / directValue) * 100).toFixed(2));
}

function summaryText(report) {
  const direct = report.endpoints.ranking_direct;
  const cache = report.endpoints.ranking_cache;
  const comparison = report.comparison;

  return [
    '',
    `k6 summary written to ${SUMMARY_PATH}`,
    `[Ranking Direct] avg=${direct.avg_ms}ms p95=${direct.p95_ms}ms rps=${direct.rps} fail=${direct.fail_rate}`,
    `[Ranking Cache] avg=${cache.avg_ms}ms p95=${cache.p95_ms}ms rps=${cache.rps} fail=${cache.fail_rate}`,
    `[Improvement] avg=${comparison.avg_latency_improvement_pct}% p95=${comparison.p95_latency_improvement_pct}% rps=${comparison.rps_gain_pct}%`,
    '',
  ].join('\n');
}

export function handleSummary(data) {
  const rankingDirect = endpointSummary(
    'Ranking Direct',
    RANKING_DIRECT_URL,
    data.metrics.ranking_direct_duration,
    data.metrics.ranking_direct_requests,
    data.metrics.ranking_direct_failures,
  );
  const rankingCache = endpointSummary(
    'Ranking Cache',
    RANKING_CACHE_URL,
    data.metrics.ranking_cache_duration,
    data.metrics.ranking_cache_requests,
    data.metrics.ranking_cache_failures,
  );

  const report = {
    generated_at: new Date().toISOString(),
    scenario: TEST_PROFILE,
    endpoints: {
      ranking_direct: rankingDirect,
      ranking_cache: rankingCache,
    },
    comparison: {
      avg_latency_improvement_pct: improvement(rankingDirect.avg_ms, rankingCache.avg_ms),
      p95_latency_improvement_pct: improvement(rankingDirect.p95_ms, rankingCache.p95_ms),
      rps_gain_pct: gain(rankingCache.rps, rankingDirect.rps),
    },
  };

  return {
    [SUMMARY_PATH]: JSON.stringify(report, null, 2),
    stdout: summaryText(report),
  };
}
