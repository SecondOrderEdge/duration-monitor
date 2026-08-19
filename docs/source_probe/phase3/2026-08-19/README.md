# Phase 3 source discovery

- Probe run (UTC): `2026-08-19T00:45:53.892955+00:00`

What each candidate publisher actually returns. This is DISCOVERY — no field names are declared yet, so nothing here is verified. It exists so the Phase 3 schema is designed against observed responses rather than assumptions, which is what the Phase 1 probe was for.

| source | publisher | reachable | would feed |
|---|---|---|---|
| `ecb` | European Central Bank | **no** | bill share, net issuance, term premium inputs |

## `ecb` — European Central Bank

Securities issues statistics and government finance statistics cover Germany, France and Italy on one basis, which is three of the five Phase 3 sovereigns from a single publisher.

### `https://data-api.ecb.europa.eu/service/dataflow/ECB`

- **error**: `ProxyError: HTTPSConnectionPool(host='data-api.ecb.europa.eu', port=443): Max retries exceeded with url: /service/dataflow/ECB (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`
- network egress policy denial, not source failure

### `https://data-api.ecb.europa.eu/service/data/SEC?lastNObservations=1&format=jsondata`

- **error**: `ProxyError: HTTPSConnectionPool(host='data-api.ecb.europa.eu', port=443): Max retries exceeded with url: /service/data/SEC?lastNObservations=1&format=jsondata (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`
- network egress policy denial, not source failure
