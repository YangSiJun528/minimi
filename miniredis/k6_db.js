import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 20,
  duration: '10s',
  summaryTrendStats: ['avg', 'p(95)', 'min', 'med', 'max'],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export default function () {
  const response = http.get(`${BASE_URL}/db-direct?id=1`);

  check(response, {
    'db-direct status is 200': (r) => r.status === 200,
  });
}
