from __future__ import annotations

import math
import random
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


CatalogProduct = dict[str, Any]
RankingPayload = dict[str, Any]


class SlowDemoDatabase:
    def __init__(self) -> None:
        self._catalog = self._build_catalog(catalog_size=1000)
        self._preview_snapshot = self._calculate_top_ranking(limit=5)

    def compute_top_ranking(self, limit: int = 10) -> tuple[RankingPayload, int]:
        delay_ms = random.randint(100, 200)
        time.sleep(delay_ms / 1000)
        return self._calculate_top_ranking(limit=limit), delay_ms

    def preview_top_ranking(self, limit: int = 5) -> RankingPayload:
        if limit == 5:
            return deepcopy(self._preview_snapshot)

        return self._calculate_top_ranking(limit=limit)

    def _build_catalog(self, catalog_size: int) -> list[CatalogProduct]:
        rng = random.Random(20260318)
        brands = ["Minimi", "Layerd", "Harbor", "Nomad", "Frame", "Tide", "Rivet", "Melo"]
        adjectives = ["Soft", "Urban", "Classic", "Light", "Daily", "Modern", "Prime", "Studio"]
        categories = ["Jacket", "Shirt", "Knit", "Denim", "Sneaker", "Coat", "Bag", "Pants"]

        catalog: list[CatalogProduct] = []
        for index in range(1, catalog_size + 1):
            category = categories[index % len(categories)]
            brand = brands[(index * 3) % len(brands)]
            adjective = adjectives[(index * 5) % len(adjectives)]
            base_views = 2800 + (index % 35) * 140 + rng.randint(0, 420)
            daily_metrics: list[dict[str, int]] = []

            for day in range(1, 29):
                freshness_bonus = max(0.72, 1.32 - (day * 0.018))
                weekday_bias = 1.08 if day % 7 in {5, 6} else 0.96
                demand_wave = 0.9 + ((index + day) % 11) * 0.03

                views = int(base_views * freshness_bonus * weekday_bias * demand_wave)
                likes = max(8, int(views * (0.048 + ((index + day) % 6) * 0.004)))
                wishlists = max(5, int(views * (0.031 + ((index + day * 2) % 5) * 0.003)))
                sales = max(2, int(views * (0.011 + ((index + day * 3) % 4) * 0.0018)))
                repeat_buyers = max(1, int(sales * (0.21 + ((index + day) % 4) * 0.04)))

                daily_metrics.append(
                    {
                        "views": views,
                        "likes": likes,
                        "wishlists": wishlists,
                        "sales": sales,
                        "repeat_buyers": repeat_buyers,
                    }
                )

            catalog.append(
                {
                    "product_id": f"SKU-{index:04d}",
                    "name": f"{adjective} {category} {index}",
                    "brand": brand,
                    "category": category,
                    "price_krw": 39000 + (index % 24) * 3200,
                    "review_score": round(3.8 + ((index * 7) % 12) * 0.1, 1),
                    "review_count": 48 + (index % 90) * 5,
                    "return_rate": round(0.018 + ((index * 11) % 7) * 0.004, 4),
                    "inventory_left": 28 + (index % 310),
                    "days_since_launch": 6 + (index % 240),
                    "daily_metrics": daily_metrics,
                }
            )

        return catalog

    def _calculate_top_ranking(self, limit: int) -> RankingPayload:
        scored_products: list[dict[str, Any]] = []

        for product in self._catalog:
            weighted_demand = 0.0
            weighted_engagement = 0.0
            weighted_sales = 0.0
            total_views = 0
            total_likes = 0
            total_wishlists = 0
            total_sales = 0
            total_repeat_buyers = 0

            for day_index, metrics in enumerate(product["daily_metrics"], start=1):
                weight = 1.0 + day_index * 0.09
                views = metrics["views"]
                likes = metrics["likes"]
                wishlists = metrics["wishlists"]
                sales = metrics["sales"]
                repeat_buyers = metrics["repeat_buyers"]

                total_views += views
                total_likes += likes
                total_wishlists += wishlists
                total_sales += sales
                total_repeat_buyers += repeat_buyers

                weighted_demand += (views * 0.018 + likes * 2.8 + wishlists * 2.1) * weight
                weighted_engagement += ((likes + wishlists) / max(views, 1)) * 120 * weight
                weighted_sales += (sales * 9.2 + repeat_buyers * 6.4) * weight

            conversion_rate = total_sales / max(total_views, 1)
            wishlist_rate = total_wishlists / max(total_views, 1)
            quality_boost = product["review_score"] * math.log1p(product["review_count"]) * 18
            loyalty_boost = math.log1p(total_repeat_buyers) * 26
            freshness_boost = 140 / (product["days_since_launch"] + 18)
            scarcity_boost = max(0.82, 1.18 - product["inventory_left"] / 900)
            return_penalty = product["return_rate"] * 220
            price_efficiency = 180 / math.sqrt(product["price_krw"])

            score = (
                weighted_demand * 0.42
                + weighted_engagement * 0.18
                + weighted_sales * 0.34
                + conversion_rate * 22000
                + wishlist_rate * 6000
                + quality_boost
                + loyalty_boost
                + freshness_boost
                + price_efficiency
            ) * scarcity_boost - return_penalty

            scored_products.append(
                {
                    "product_id": product["product_id"],
                    "name": product["name"],
                    "brand": product["brand"],
                    "category": product["category"],
                    "price_krw": product["price_krw"],
                    "score": round(score, 2),
                    "views_28d": total_views,
                    "likes_28d": total_likes,
                    "wishlists_28d": total_wishlists,
                    "sales_28d": total_sales,
                    "conversion_pct": round(conversion_rate * 100, 2),
                    "review_score": product["review_score"],
                    "days_since_launch": product["days_since_launch"],
                }
            )

        scored_products.sort(key=lambda item: item["score"], reverse=True)
        top_products = []

        for rank, product in enumerate(scored_products[:limit], start=1):
            ranked_product = deepcopy(product)
            ranked_product["rank"] = rank
            top_products.append(ranked_product)

        return {
            "ranking_name": "Outerwear Momentum Ranking",
            "algorithm_version": "views+likes+wishlists+sales+reviews+repeat-buyers+freshness",
            "catalog_size": len(self._catalog),
            "top_n": limit,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "top_products": top_products,
        }
