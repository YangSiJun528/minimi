from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from threading import Lock
from typing import Any, Literal


CacheStatus = Literal["hit", "miss", "bypass"]

CATEGORY_IMAGE_MAP = {
    "Jacket": "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=900&q=80",
    "Shirt": "https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=900&q=80",
    "Knit": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=900&q=80",
    "Denim": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=900&q=80",
    "Sneaker": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80",
    "Coat": "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?auto=format&fit=crop&w=900&q=80",
    "Bag": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=900&q=80",
    "Pants": "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=900&q=80",
}


@dataclass(slots=True)
class EndpointMetrics:
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_duration_ms: float | None = None
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    recent_durations_ms: deque[float] = field(default_factory=lambda: deque(maxlen=40))

    def record(self, duration_ms: float, success: bool, cache_status: CacheStatus | None = None) -> None:
        self.total_requests += 1
        self.last_duration_ms = duration_ms
        self.recent_durations_ms.append(duration_ms)
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        if cache_status == "hit":
            self.cache_hit_count += 1
        elif cache_status == "miss":
            self.cache_miss_count += 1

    def snapshot(self) -> dict[str, Any]:
        avg = mean(self.recent_durations_ms) if self.recent_durations_ms else None
        total_cache = self.cache_hit_count + self.cache_miss_count
        hit_rate = (self.cache_hit_count / total_cache * 100) if total_cache else None
        return {
            "avg_duration_ms": None if avg is None else round(avg, 2),
            "cache_hit_count": self.cache_hit_count,
            "cache_miss_count": self.cache_miss_count,
            "cache_hit_rate_pct": None if hit_rate is None else round(hit_rate, 1),
        }


class DemoMetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._ranking_direct = EndpointMetrics()
        self._ranking_cache = EndpointMetrics()

    def record_ranking_direct(self, duration_ms: float, success: bool) -> None:
        with self._lock:
            self._ranking_direct.record(duration_ms, success, "bypass")

    def record_ranking_cache(self, duration_ms: float, success: bool, cache_status: CacheStatus) -> None:
        with self._lock:
            self._ranking_cache.record(duration_ms, success, cache_status)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ranking_direct": self._ranking_direct.snapshot(),
                "ranking_cache": self._ranking_cache.snapshot(),
            }


def _read_report(report_path: Path) -> dict[str, Any] | None:
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _decorate_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for product in products:
        item = dict(product)
        item["image_url"] = CATEGORY_IMAGE_MAP.get(product.get("category"), CATEGORY_IMAGE_MAP["Shirt"])
        result.append(item)
    return result


def build_dashboard_payload(metrics_store: DemoMetricsStore, report_path: Path, ranking_preview: dict[str, Any]) -> dict[str, Any]:
    metrics = metrics_store.snapshot()
    products = _decorate_products(ranking_preview.get("top_products", []))
    top = products[0] if products else None
    report = _read_report(report_path)
    comparison = report.get("comparison", {}) if report else {}
    endpoints = report.get("endpoints", {}) if report else {}
    direct = endpoints.get("ranking_direct", {})
    cache = endpoints.get("ranking_cache", {})
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "hero": {
            "eyebrow": "MINI REDIS FASHION DEMO",
            "title": "랭킹은 그대로, 체감 속도만 빠르게",
            "subtitle": f"지금 1위는 {top['brand']}의 {top['name']}입니다." if top else "상위 상품을 불러오는 중입니다.",
            "chips": ["실시간 비교", "TTL 5초"],
            "featured": top,
        },
        "ranking_preview": {**ranking_preview, "top_products": products},
        "collections": [
            {"title": "지금 뜨는 상품", "products": products[:3]},
            {"title": "위시가 높은 상품", "products": sorted(products, key=lambda item: item["wishlists_28d"], reverse=True)[:3]},
            {"title": "전환이 강한 상품", "products": sorted(products, key=lambda item: item["conversion_pct"], reverse=True)[:3]},
        ],
        "signals": [
            {"title": "수요", "copy": "조회, 좋아요, 위시리스트 같은 관심 신호를 반영합니다."},
            {"title": "판매", "copy": "판매량과 재구매 흐름이 강한 상품이 위로 올라옵니다."},
            {"title": "리뷰", "copy": "리뷰 품질과 반품 패널티까지 함께 계산합니다."},
        ],
        "cache_demo": {
            "ttl_seconds": 5,
            "cache_hit_rate_pct": metrics["ranking_cache"].get("cache_hit_rate_pct"),
            "cache_hits": metrics["ranking_cache"].get("cache_hit_count", 0),
            "cache_misses": metrics["ranking_cache"].get("cache_miss_count", 0),
            "cache_avg_ms": metrics["ranking_cache"].get("avg_duration_ms"),
            "direct_avg_ms": metrics["ranking_direct"].get("avg_duration_ms"),
        },
        "k6_compare": {
            "available": report is not None,
            "avg_ms": {
                "direct": direct.get("avg_ms"),
                "cache": cache.get("avg_ms"),
                "improvement_pct": comparison.get("avg_latency_improvement_pct"),
            },
            "p95_ms": {
                "direct": direct.get("p95_ms"),
                "cache": cache.get("p95_ms"),
                "improvement_pct": comparison.get("p95_latency_improvement_pct"),
            },
            "rps": {
                "direct": direct.get("rps"),
                "cache": cache.get("rps"),
                "improvement_pct": comparison.get("rps_gain_pct"),
            },
        },
        "proof": {
            "cards": []
            if not report
            else [
                {
                    "label": "평균 응답",
                    "value": f"{comparison.get('avg_latency_improvement_pct', 0):.1f}%",
                    "detail": f"직접 {direct.get('avg_ms', 0):.0f}ms / 캐시 {cache.get('avg_ms', 0):.0f}ms",
                },
                {
                    "label": "P95 응답",
                    "value": f"{comparison.get('p95_latency_improvement_pct', 0):.1f}%",
                    "detail": f"직접 {direct.get('p95_ms', 0):.0f}ms / 캐시 {cache.get('p95_ms', 0):.0f}ms",
                },
                {
                    "label": "처리량",
                    "value": f"{comparison.get('rps_gain_pct', 0):.1f}%",
                    "detail": f"직접 {direct.get('rps', 0):.1f}rps / 캐시 {cache.get('rps', 0):.1f}rps",
                },
            ],
        },
    }


def build_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>미니미 쇼룸</title>
  <style>
    :root{--panel:rgba(16,22,46,.78);--line:rgba(173,188,255,.14);--text:#eef3ff;--muted:#aeb9dc;--accent:#9ad1ff;--accent2:#d478ff;--radius:24px;--shadow:0 22px 64px rgba(2,4,14,.42)}
    *{box-sizing:border-box}
    body{margin:0;color:var(--text);font-family:"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;background:radial-gradient(circle at 20% 20%, rgba(122,142,255,.28), transparent 22%),radial-gradient(circle at 80% 15%, rgba(212,120,255,.18), transparent 18%),radial-gradient(circle at 50% 80%, rgba(80,150,255,.15), transparent 26%),linear-gradient(180deg,#070a18 0%,#0a1023 48%,#050814 100%);min-height:100vh}
    body:before{content:"";position:fixed;inset:0;pointer-events:none;background-image:radial-gradient(circle, rgba(255,255,255,.7) 0 1px, transparent 1.5px),radial-gradient(circle, rgba(255,255,255,.35) 0 1px, transparent 1.5px);background-size:160px 160px,240px 240px;background-position:0 0,60px 80px;opacity:.18}
    .page{width:min(1220px,calc(100vw - 28px));margin:0 auto;padding:18px 0 44px;position:relative;z-index:1}
    .panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);backdrop-filter:blur(16px)}
    .topbar{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:16px 20px;border:1px solid var(--line);border-radius:999px;background:rgba(10,14,30,.62);position:sticky;top:14px;z-index:5}
    .brand{display:flex;align-items:center;gap:10px;font-weight:700}
    .brand-mark{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#09101f}
    .nav{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:.9rem}
    .hero{display:grid;grid-template-columns:1.05fr .95fr;gap:18px;margin:20px 0 18px}
    .hero-copy,.featured-card,.collection,.signal-card,.proof-card,.panel-block,.operator,.k6-panel{padding:16px}
    .eyebrow{font-size:.76rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
    h1{margin:0 0 10px;font-size:clamp(2rem,3vw,3.4rem);line-height:1.08;letter-spacing:-.05em;max-width:14ch}
    h2{margin:0;font-size:clamp(1.35rem,2.3vw,2rem);letter-spacing:-.04em}
    h3{margin:0 0 6px;font-size:1rem}
    p{margin:0;color:var(--muted);line-height:1.6}
    .hero-sub{max-width:32ch}
    .chip-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
    .chip{padding:8px 11px;border-radius:999px;border:1px solid var(--line);background:rgba(255,255,255,.04);color:var(--muted);font-size:.85rem}
    .hero-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
    .btn{border:0;border-radius:999px;padding:12px 15px;cursor:pointer;transition:transform .2s ease,opacity .2s ease}
    .btn:hover{transform:translateY(-1px)}
    .btn-primary{background:linear-gradient(135deg,var(--accent),#b6a7ff);color:#09101f}
    .btn-secondary{background:rgba(255,255,255,.04);color:var(--text);border:1px solid var(--line)}
    .hero-demo{margin-top:18px;padding-top:18px;border-top:1px solid var(--line)}
    .compare-stats,.stat-strip,.collections,.signals,.proof-grid,.k6-summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
    .stat-box,.k6-summary-card{padding:14px;border-radius:18px;background:rgba(255,255,255,.04);border:1px solid var(--line)}
    .stat-box strong,.k6-summary-card strong{display:block;margin-top:6px;font-size:1.35rem}
    .results-log{margin:0;padding:16px;border-radius:18px;background:rgba(6,9,20,.92);border:1px solid var(--line);color:#dbe6ff;min-height:144px;white-space:pre-wrap;font:0.9rem/1.6 Consolas,Monaco,monospace}
    .hero-side{display:grid;gap:12px}
    .featured-image{width:100%;aspect-ratio:4/5;border-radius:20px;overflow:hidden;background:#111;margin-bottom:12px}
    .featured-image img{width:100%;height:100%;object-fit:cover;display:block}
    .featured-meta{display:grid;gap:6px}
    .section{margin-top:18px}
    .section-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(240px,360px);gap:16px;align-items:end;margin-bottom:14px}
    .k6-shell{display:grid;grid-template-columns:.95fr 1.05fr;gap:16px}
    .k6-chart{padding:16px;border-radius:20px;background:rgba(8,11,24,.78);border:1px solid var(--line);display:grid;gap:14px}
    .k6-bar-group{display:grid;gap:8px}
    .k6-bar-head{display:flex;justify-content:space-between;gap:12px;align-items:end}
    .k6-track{display:grid;gap:8px}
    .k6-bar-row{display:grid;grid-template-columns:64px 1fr auto;gap:10px;align-items:center}
    .k6-bar-label{font-size:.82rem;color:var(--muted)}
    .k6-bar-fill{height:12px;border-radius:999px;overflow:hidden;background:rgba(255,255,255,.07);border:1px solid rgba(173,188,255,.1)}
    .k6-bar-fill span{display:block;height:100%;border-radius:inherit}
    .k6-bar-fill .direct{background:linear-gradient(90deg,rgba(255,140,164,.95),rgba(255,103,120,.82))}
    .k6-bar-fill .cache{background:linear-gradient(90deg,rgba(154,209,255,.96),rgba(120,133,255,.82))}
    .k6-bar-value{font-size:.84rem;color:var(--text);min-width:74px;text-align:right}
    .k6-empty{padding:24px;border-radius:20px;border:1px dashed var(--line);background:rgba(255,255,255,.03);color:var(--muted)}
    .collection-grid{display:grid;gap:10px;margin-top:12px}
    .product-card{display:grid;grid-template-columns:92px minmax(0,1fr);gap:10px;padding:10px;border-radius:18px;background:rgba(255,255,255,.04);border:1px solid var(--line);align-items:center}
    .product-thumb{width:92px;height:108px;border-radius:14px;overflow:hidden;background:#111}
    .product-thumb img{width:100%;height:100%;object-fit:cover;display:block}
    .product-kicker{font-size:.76rem;color:var(--muted);margin-bottom:4px}
    .product-name{font-size:.96rem;font-weight:700;line-height:1.28}
    .meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;color:var(--muted);font-size:.86rem}
    .ranking-grid{display:grid;gap:8px}
    .ranking-row{display:grid;grid-template-columns:48px 1.25fr .8fr .8fr .8fr .7fr;gap:10px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line);font-size:.9rem}
    .pill{display:inline-flex;justify-content:center;align-items:center;padding:6px 10px;border-radius:999px;background:rgba(154,209,255,.12);color:var(--accent);font-size:.76rem}
    .proof-card strong{display:block;font-size:1.8rem;margin-top:8px}
    details{border:1px solid var(--line);border-radius:22px;background:rgba(10,14,30,.58);overflow:hidden}
    summary{cursor:pointer;list-style:none;padding:16px 18px;font-weight:700}
    summary::-webkit-details-marker{display:none}
    .operator-body{padding:0 18px 18px;display:grid;grid-template-columns:1fr 1fr;gap:16px}
    .field{display:grid;gap:6px;margin-bottom:10px}
    label{font-size:.86rem;color:var(--muted)}
    input,textarea{width:100%;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.04);color:var(--text);font:inherit}
    textarea{min-height:100px;resize:vertical}
    .fine{color:var(--muted);font-size:.88rem;line-height:1.6}
    .empty{padding:14px 0;color:var(--muted)}
    .reveal{opacity:.18;transform:translateY(24px) scale(.985);transition:opacity .55s ease,transform .55s cubic-bezier(.22,1,.36,1)}
    .reveal.is-visible{opacity:1;transform:none}
    @media (max-width:1080px){.hero,.section-head,.operator-body,.collections,.signals,.proof-grid,.compare-stats,.stat-strip,.k6-shell,.k6-summary-grid{grid-template-columns:1fr}.ranking-row{grid-template-columns:42px 1fr}.ranking-row>:nth-child(n+3){justify-self:start}}
    @media (max-width:720px){.page{width:min(100vw - 18px,1220px)}.hero-copy,.featured-card,.collection,.signal-card,.proof-card,.panel-block,.operator,.k6-panel{padding:14px}.product-card{grid-template-columns:82px 1fr}.product-thumb{width:82px;height:98px}h1{max-width:none;font-size:clamp(1.8rem,8vw,2.7rem)}}
  </style>
</head>
<body>
  <div class="page">
    <header class="topbar">
      <div class="brand"><div class="brand-mark">M</div><span>미니미 쇼룸</span></div>
      <nav class="nav"><span>컬렉션</span><span>랭킹</span><span>캐시</span><span>성능</span></nav>
    </header>

    <section class="hero reveal">
      <div class="panel hero-copy">
        <div class="eyebrow" id="hero-eyebrow">MINI REDIS FASHION DEMO</div>
        <h1 id="hero-title">랭킹은 그대로, 체감 속도만 빠르게</h1>
        <p class="hero-sub" id="hero-subtitle">상위 상품을 불러오는 중입니다.</p>
        <div class="chip-row" id="hero-chips"></div>
        <div class="hero-actions">
          <button class="btn btn-primary" id="compare-cache" type="button">캐시 랭킹</button>
          <button class="btn btn-secondary" id="compare-direct" type="button">직접 랭킹</button>
        </div>
        <div class="hero-demo">
          <div class="compare-stats">
            <div class="stat-box"><div>실시간 캐시 적중률</div><strong id="live-hit-rate">-</strong></div>
            <div class="stat-box"><div>캐시 평균 응답</div><strong id="live-cache-avg">-</strong></div>
            <div class="stat-box"><div>직접 평균 응답</div><strong id="live-direct-avg">-</strong></div>
          </div>
          <pre class="results-log" id="result-log">다음 시연 요청을 기다리는 중입니다.</pre>
        </div>
      </div>
      <div class="hero-side">
        <article class="panel featured-card reveal">
          <div class="featured-image"><img id="featured-image" alt="대표 상품 이미지" /></div>
          <div class="featured-meta">
            <h3 id="featured-name">대표 상품</h3>
            <p id="featured-copy">데이터를 불러오는 중입니다.</p>
          </div>
        </article>
        <div class="stat-strip">
          <div class="stat-box reveal"><div>TTL</div><strong id="cache-ttl">5초</strong></div>
          <div class="stat-box reveal"><div>평균 개선</div><strong id="proof-lift">-</strong></div>
          <div class="stat-box reveal"><div>캐시 적중률</div><strong id="live-hit-rate-hero">-</strong></div>
        </div>
      </div>
    </section>

    <section class="section reveal">
      <div class="panel k6-panel">
        <div class="section-head">
          <div><div class="eyebrow">K6 비교</div><h2>바로 성능을 비교합니다</h2></div>
          <p>부하 테스트 결과를 평균 응답, P95, 처리량 기준으로 막대 그래프와 수치 카드로 함께 보여줍니다.</p>
        </div>
        <div id="k6-compare-panel"></div>
      </div>
    </section>

    <section class="section reveal">
      <div class="section-head">
        <div><div class="eyebrow">상위 랭킹</div><h2>시연 결과를 바로 확인합니다</h2></div>
        <p>위 버튼을 누르면 여기에 상품 목록이 즉시 갱신됩니다.</p>
      </div>
      <div class="panel panel-block">
        <div class="ranking-grid" id="ranking-preview"></div>
      </div>
    </section>

    <section class="section reveal">
      <div class="section-head">
        <div><div class="eyebrow">컬렉션</div><h2>상위 상품만 빠르게 모아봅니다</h2></div>
        <p>설명은 짧게 두고 카드 중심으로 정리했습니다.</p>
      </div>
      <div class="collections" id="collections-grid"></div>
    </section>

    <section class="section reveal">
      <div class="section-head">
        <div><div class="eyebrow">랭킹 신호</div><h2>어떤 요소가 점수에 반영되는지 보여줍니다</h2></div>
        <p>수요, 판매, 리뷰 축만 남겨 시연 중에도 빠르게 읽히도록 했습니다.</p>
      </div>
      <div class="signals" id="signals-grid"></div>
    </section>

    <section class="section reveal">
      <details>
        <summary>운영자 실험 패널</summary>
        <div class="operator-body">
          <div class="panel operator">
            <div class="field"><label for="playground-key">키</label><input id="playground-key" value="look:home:hero" /></div>
            <div class="field"><label for="playground-value">값</label><textarea id="playground-value">{"title":"우주 룩북","badge":"editor-pick"}</textarea></div>
            <div class="field"><label for="playground-ttl">TTL</label><input id="playground-ttl" type="number" min="1" value="15" /></div>
            <div class="hero-actions">
              <button class="btn btn-primary" id="playground-set" type="button">저장</button>
              <button class="btn btn-secondary" id="playground-get" type="button">조회</button>
              <button class="btn btn-secondary" id="playground-delete" type="button">삭제</button>
            </div>
          </div>
          <div class="panel operator">
            <pre class="results-log" id="playground-log">플레이그라운드 응답이 여기에 표시됩니다.</pre>
            <p class="fine">메인 시연을 방해하지 않도록 접어둘 수 있게 유지했습니다.</p>
          </div>
        </div>
      </details>
    </section>
  </div>

  <script>
    function fmtNumber(v){if(v===null||v===undefined||Number.isNaN(Number(v)))return "-";return new Intl.NumberFormat("ko-KR").format(Number(v))}
    function fmtMs(v){if(v===null||v===undefined)return "-";return `${Number(v).toFixed(0)}ms`}
    function fmtPct(v){if(v===null||v===undefined)return "-";return `${Number(v).toFixed(1)}%`}
    function fmtPrice(v){if(v===null||v===undefined)return "-";return `${new Intl.NumberFormat("ko-KR").format(Number(v))}원`}
    function fmtRps(v){if(v===null||v===undefined)return "-";return `${Number(v).toFixed(1)} rps`}
    function setText(id,v){const el=document.getElementById(id);if(el)el.textContent=v}
    function appendLog(id,message,clear=false){const target=document.getElementById(id);const stamp=new Date().toLocaleTimeString("ko-KR");target.textContent=clear?`[${stamp}] ${message}`:`${target.textContent}\n[${stamp}] ${message}`}
    let revealObserver = null
    function activateReveal(){
      const items = document.querySelectorAll(".reveal")
      if(window.matchMedia("(prefers-reduced-motion: reduce)").matches){items.forEach((item)=>item.classList.add("is-visible"));return}
      if(!revealObserver){
        revealObserver = new IntersectionObserver((entries)=>{entries.forEach((entry)=>{entry.target.classList.toggle("is-visible", entry.isIntersecting)})},{threshold:.18})
      }
      items.forEach((item)=>revealObserver.observe(item))
    }
    function renderHero(data){
      const hero = data.hero || {}
      const featured = hero.featured || {}
      setText("hero-eyebrow", hero.eyebrow || "MINI REDIS FASHION DEMO")
      setText("hero-title", hero.title || "랭킹은 그대로, 체감 속도만 빠르게")
      setText("hero-subtitle", hero.subtitle || "상위 상품을 불러오는 중입니다.")
      setText("featured-name", featured.name || "대표 상품")
      setText("featured-copy", featured.name ? `${featured.brand} / ${fmtPrice(featured.price_krw)} / 전환율 ${fmtPct(featured.conversion_pct)}` : "데이터를 불러오는 중입니다.")
      document.getElementById("featured-image").src = featured.image_url || ""
      const chips = document.getElementById("hero-chips")
      chips.innerHTML = ""
      ;(hero.chips || []).forEach((chip)=>{const el=document.createElement("span");el.className="chip";el.textContent=chip;chips.appendChild(el)})
    }
    function renderCollections(data){
      const grid = document.getElementById("collections-grid")
      grid.innerHTML = ""
      ;(data.collections || []).forEach((collection)=>{const card=document.createElement("article");card.className="panel collection reveal";card.innerHTML=`<div class="eyebrow">${collection.title}</div><h3>${collection.title}</h3><div class="collection-grid">${(collection.products || []).map((product)=>`<article class="product-card"><div class="product-thumb"><img src="${product.image_url}" alt="${product.name}" loading="lazy" /></div><div><div class="product-kicker">#${product.rank} / ${product.brand}</div><div class="product-name">${product.name}</div><div class="meta"><span>${fmtPrice(product.price_krw)}</span><span>전환 ${fmtPct(product.conversion_pct)}</span><span>위시 ${fmtNumber(product.wishlists_28d)}</span></div></div></article>`).join("")}</div>`;grid.appendChild(card)})
    }
    function renderSignals(data){
      const grid = document.getElementById("signals-grid")
      grid.innerHTML = ""
      ;(data.signals || []).forEach((signal)=>{const card=document.createElement("article");card.className="panel signal-card reveal";card.innerHTML=`<div class="eyebrow">${signal.title}</div><h3>${signal.title}</h3><p>${signal.copy}</p>`;grid.appendChild(card)})
    }
    function renderRankingPreview(products){
      const container = document.getElementById("ranking-preview")
      if(!products || !products.length){container.innerHTML='<div class="empty">랭킹 데이터를 불러오지 못했습니다.</div>';return}
      container.innerHTML = products.map((product)=>`<div class="ranking-row"><div class="pill">#${product.rank}</div><div><strong>${product.name}</strong><br /><span class="fine">${product.brand} / ${product.category}</span></div><div>${fmtPrice(product.price_krw)}</div><div>조회 ${fmtNumber(product.views_28d)}</div><div>판매 ${fmtNumber(product.sales_28d)}</div><div>${product.score}</div></div>`).join("")
    }
    function renderK6Compare(data){
      const target = document.getElementById("k6-compare-panel")
      const compare = data.k6_compare || {}
      if(!compare.available){
        target.innerHTML = '<div class="k6-empty">k6 비교 리포트가 아직 없습니다. 테스트 결과가 생성되면 여기에 바로 표시됩니다.</div>'
        return
      }
      const metrics = [
        {key:"avg_ms", label:"평균 응답", formatter:fmtMs, largerBetter:false},
        {key:"p95_ms", label:"P95 응답", formatter:fmtMs, largerBetter:false},
        {key:"rps", label:"처리량", formatter:fmtRps, largerBetter:true},
      ]
      const summary = metrics.map((metric)=>{
        const item = compare[metric.key] || {}
        return `<article class="k6-summary-card reveal"><div class="eyebrow">${metric.label}</div><strong>${fmtPct(item.improvement_pct)}</strong><div class="fine">직접 ${metric.formatter(item.direct)} / 캐시 ${metric.formatter(item.cache)}</div></article>`
      }).join("")
      const bars = metrics.map((metric)=>{
        const item = compare[metric.key] || {}
        const direct = Number(item.direct || 0)
        const cache = Number(item.cache || 0)
        const baseline = Math.max(direct, cache, 1)
        return `<div class="k6-bar-group">
          <div class="k6-bar-head">
            <strong>${metric.label}</strong>
            <span class="fine">${fmtPct(item.improvement_pct)} ${metric.largerBetter ? "향상" : "단축"}</span>
          </div>
          <div class="k6-track">
            <div class="k6-bar-row">
              <div class="k6-bar-label">직접</div>
              <div class="k6-bar-fill"><span class="direct" style="width:${Math.max(8, direct / baseline * 100)}%"></span></div>
              <div class="k6-bar-value">${metric.formatter(item.direct)}</div>
            </div>
            <div class="k6-bar-row">
              <div class="k6-bar-label">캐시</div>
              <div class="k6-bar-fill"><span class="cache" style="width:${Math.max(8, cache / baseline * 100)}%"></span></div>
              <div class="k6-bar-value">${metric.formatter(item.cache)}</div>
            </div>
          </div>
        </div>`
      }).join("")
      target.innerHTML = `<div class="k6-shell"><div class="k6-summary-grid">${summary}</div><div class="k6-chart reveal">${bars}</div></div>`
    }
    function renderProof(data){
      const proof = data.proof || {}
      const cacheDemo = data.cache_demo || {}
      setText("cache-ttl", `${cacheDemo.ttl_seconds || 5}초`)
      setText("proof-lift", proof.cards?.[0]?.value || "-")
      setText("live-hit-rate-hero", fmtPct(cacheDemo.cache_hit_rate_pct))
      setText("live-hit-rate", fmtPct(cacheDemo.cache_hit_rate_pct))
      setText("live-cache-avg", fmtMs(cacheDemo.cache_avg_ms))
      setText("live-direct-avg", fmtMs(cacheDemo.direct_avg_ms))
      setText("proof-copy", proof.cards?.length ? "측정된 k6 결과를 반영했습니다." : "표시할 측정 카드가 아직 없습니다.")
      const grid = document.getElementById("proof-grid")
      grid.innerHTML = (proof.cards || []).length ? (proof.cards || []).map((card)=>`<article class="panel proof-card reveal"><div class="eyebrow">${card.label}</div><strong>${card.value}</strong><div class="fine">${card.detail}</div></article>`).join("") : '<article class="panel proof-card reveal"><div class="empty">표시할 성능 카드가 없습니다.</div></article>'
    }
    async function loadDashboard(){
      const response = await fetch("/dashboard-data")
      if(!response.ok) throw new Error("dashboard-data failed")
      const data = await response.json()
      renderHero(data)
      renderCollections(data)
      renderSignals(data)
      renderRankingPreview(data.ranking_preview?.top_products || [])
      renderK6Compare(data)
      renderProof(data)
      activateReveal()
    }
    async function runRequest(url, label){
      const started = performance.now()
      const response = await fetch(url)
      const elapsed = performance.now() - started
      const payload = await response.json()
      if(!response.ok) throw new Error(payload.detail || `${label} 실패`)
      appendLog("result-log", `${label} / ${payload.cache_status} / ${payload.source} / ${elapsed.toFixed(0)}ms`, true)
      renderRankingPreview(payload.ranking?.top_products || [])
      await loadDashboard()
      return payload
    }
    async function playgroundRequest(method){
      const key = document.getElementById("playground-key").value.trim()
      const ttlValue = document.getElementById("playground-ttl").value.trim()
      const rawValue = document.getElementById("playground-value").value.trim()
      let response
      if(method === "set"){
        let parsedValue = rawValue
        try { parsedValue = JSON.parse(rawValue) } catch (_error) {}
        response = await fetch("/demo-store", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({key, value: parsedValue, ttl_seconds: ttlValue ? Number(ttlValue) : null})})
      } else if(method === "get"){
        response = await fetch(`/demo-store?key=${encodeURIComponent(key)}`)
      } else {
        response = await fetch(`/demo-store?key=${encodeURIComponent(key)}`, { method: "DELETE" })
      }
      const payload = await response.json()
      appendLog("playground-log", JSON.stringify(payload, null, 2), true)
    }
    document.getElementById("compare-cache").addEventListener("click", ()=>runRequest("/ranking-cache", "캐시 랭킹").catch((error)=>appendLog("result-log", error.message, true)))
    document.getElementById("compare-direct").addEventListener("click", ()=>runRequest("/ranking-direct", "직접 랭킹").catch((error)=>appendLog("result-log", error.message, true)))
    document.getElementById("playground-set").addEventListener("click", ()=>playgroundRequest("set").catch((error)=>appendLog("playground-log", error.message, true)))
    document.getElementById("playground-get").addEventListener("click", ()=>playgroundRequest("get").catch((error)=>appendLog("playground-log", error.message, true)))
    document.getElementById("playground-delete").addEventListener("click", ()=>playgroundRequest("delete").catch((error)=>appendLog("playground-log", error.message, true)))
    loadDashboard().catch((error)=>appendLog("result-log", `초기 로딩 실패: ${error.message}`, true))
  </script>
</body>
</html>"""
