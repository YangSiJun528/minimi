import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = __ENV.MINIREDIS_BASE_URL || 'http://localhost:8000';
const VUS = Number(__ENV.VUS || 100);
const ITERATIONS_PER_VU = Number(__ENV.ITERATIONS_PER_VU || 10);
const failureRate = new Rate('miniredis_rmw_failures');

export const options = {
  scenarios: {
    rmw_failure: {
      executor: 'per-vu-iterations',
      vus: VUS,
      iterations: ITERATIONS_PER_VU,
      maxDuration: '1m',
      gracefulStop: '0s',
    },
  },
  thresholds: {
    miniredis_rmw_failures: ['rate==0'],
  },
};

function postJson(path, payload) {
  return http.post(`${BASE_URL}${path}`, JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
  });
}

function getJson(path) {
  return http.get(`${BASE_URL}${path}`);
}

function recordFailure(response, label) {
  const ok = check(response, {
    [`${label} returned 200`]: (res) => res.status === 200,
  });
  failureRate.add(!ok);
}

export function setup() {
  const key = __ENV.KEY || `k6-rmw-${Date.now()}`;
  const response = postJson('/set', { key, value: 0 });
  recordFailure(response, 'set');
  return {
    key,
    expected: VUS * ITERATIONS_PER_VU,
  };
}

export default function (data) {
  const getResponse = getJson(`/get?key=${encodeURIComponent(data.key)}`);
  recordFailure(getResponse, 'get');

  const current = Number(getResponse.json().value ?? 0);
  const nextValue = current + 1;

  sleep(Math.random() * 0.01);

  const setResponse = postJson('/set', { key: data.key, value: nextValue });
  recordFailure(setResponse, 'set');
}

export function teardown(data) {
  const response = getJson(`/get?key=${encodeURIComponent(data.key)}`);
  recordFailure(response, 'get');

  const body = response.json();
  const actual = Number(body.value ?? 0);
  const loss = data.expected - actual;

  console.log(
    `[MiniRedis RMW] key=${data.key} expected=${data.expected} actual=${actual} loss=${loss}`,
  );

  if (actual >= data.expected) {
    throw new Error(
      `RMW failure scenario did not reproduce lost update: expected less than ${data.expected}, got ${actual}`,
    );
  }
}
