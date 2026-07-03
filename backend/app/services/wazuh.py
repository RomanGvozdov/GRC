"""Конектор до SIEM Wazuh: аналіз подій за період (ConMon / контроль AU-6).

Два API Wazuh:
- менеджер (типово :55000, JWT через basic-auth) — версія, зведення по агентах;
- indexer/OpenSearch (типово :9200, basic-auth) — самі події `wazuh-alerts-*`
  (агрегації за період: рівні, топ-правила, топ-агенти, добова динаміка).

Дані не покидають периметр: GRC сам ходить у Wazuh, нічого не публікує.
Рекомендовано окремі read-only облікові записи API та indexer.
"""

import httpx

from app.config import get_settings

_TIMEOUT = 15.0


class WazuhError(RuntimeError):
    """Помилка звернення до Wazuh (з'єднання/автентифікація/запит)."""


class WazuhClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_url = s.wazuh_api_url.rstrip("/")
        self.api_user = s.wazuh_api_user
        self.api_password = s.wazuh_api_password
        self.indexer_url = s.wazuh_indexer_url.rstrip("/")
        self.indexer_user = s.wazuh_indexer_user
        self.indexer_password = s.wazuh_indexer_password
        self.verify = s.wazuh_ca_bundle or s.wazuh_verify_ssl
        self.enabled = bool(s.wazuh_enabled and self.api_url)
        self.indexer_ready = bool(self.indexer_url)

    # --- Менеджер (55000) ---

    def _manager_token(self) -> str:
        try:
            resp = httpx.post(
                f"{self.api_url}/security/user/authenticate",
                auth=(self.api_user, self.api_password),
                verify=self.verify,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["data"]["token"]
        except httpx.HTTPError as exc:
            raise WazuhError(f"Автентифікація в Wazuh API не вдалася: {exc}") from exc

    def status(self) -> dict:
        """Версія менеджера + зведення по агентах (перевірка з'єднання)."""
        token = self._manager_token()
        headers = {"Authorization": f"Bearer {token}"}
        out: dict = {"connected": True, "version": None, "agents": {}}
        try:
            info = httpx.get(
                f"{self.api_url}/manager/info", headers=headers,
                verify=self.verify, timeout=_TIMEOUT,
            )
            if info.status_code == 200:
                data = info.json().get("data", {})
                items = data.get("affected_items") or [data]
                out["version"] = (items[0] or {}).get("version")
        except httpx.HTTPError:
            pass
        try:
            ag = httpx.get(
                f"{self.api_url}/agents/summary/status", headers=headers,
                verify=self.verify, timeout=_TIMEOUT,
            )
            if ag.status_code == 200:
                data = ag.json().get("data", {})
                # v4.x: {"connection": {"active": n, ...}} або плоский словник
                out["agents"] = data.get("connection", data)
        except httpx.HTTPError:
            pass
        return out

    # --- Indexer (9200): події за період ---

    def alerts_summary(self, days: int, min_level: int = 3) -> dict:
        """Агрегований аналіз подій за останні `days` діб (без вивантаження
        сирих подій): всього, за рівнями, топ-правила, топ-агенти, динаміка."""
        if not self.indexer_ready:
            raise WazuhError(
                "Не задано WAZUH_INDEXER_URL — події зберігає indexer (порт 9200), "
                "без нього доступний лише статус менеджера."
            )
        body = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"range": {"timestamp": {"gte": f"now-{days}d/d"}}},
                        {"range": {"rule.level": {"gte": min_level}}},
                    ]
                }
            },
            "aggs": {
                "by_level": {
                    "range": {
                        "field": "rule.level",
                        "ranges": [
                            {"key": "low", "from": 0, "to": 7},
                            {"key": "medium", "from": 7, "to": 12},
                            {"key": "high", "from": 12, "to": 16},
                        ],
                    }
                },
                "top_rules": {
                    "terms": {"field": "rule.description", "size": 10},
                    "aggs": {"max_level": {"max": {"field": "rule.level"}}},
                },
                "top_agents": {"terms": {"field": "agent.name", "size": 10}},
                "per_day": {
                    "date_histogram": {
                        "field": "timestamp", "calendar_interval": "day",
                    }
                },
            },
        }
        try:
            resp = httpx.post(
                f"{self.indexer_url}/wazuh-alerts-*/_search",
                json=body,
                auth=(self.indexer_user, self.indexer_password),
                verify=self.verify,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            raw = resp.json()
        except httpx.HTTPError as exc:
            raise WazuhError(f"Запит до Wazuh indexer не вдався: {exc}") from exc

        aggs = raw.get("aggregations", {})
        total_raw = raw.get("hits", {}).get("total", {})
        # OpenSearch: {"value": N, "relation": "eq"}; старі ES можуть віддати число
        total = total_raw.get("value", 0) if isinstance(total_raw, dict) else int(total_raw or 0)
        return {
            "days": days,
            "min_level": min_level,
            "total": total,
            "by_level": {
                b["key"]: b["doc_count"]
                for b in aggs.get("by_level", {}).get("buckets", [])
            },
            "top_rules": [
                {
                    "rule": b["key"],
                    "count": b["doc_count"],
                    "max_level": int(b.get("max_level", {}).get("value") or 0),
                }
                for b in aggs.get("top_rules", {}).get("buckets", [])
            ],
            "top_agents": [
                {"agent": b["key"], "count": b["doc_count"]}
                for b in aggs.get("top_agents", {}).get("buckets", [])
            ],
            "per_day": [
                {"date": b.get("key_as_string", "")[:10], "count": b["doc_count"]}
                for b in aggs.get("per_day", {}).get("buckets", [])
            ],
        }


def get_client() -> WazuhClient:
    return WazuhClient()
