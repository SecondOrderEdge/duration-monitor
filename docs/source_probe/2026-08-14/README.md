# Source probe results

- Probe run (UTC): `2026-08-14T03:02:13.817553+00:00`

Field names below are **observed from live responses**. Anything marked MISSING means `config/sources.yaml` expected a field the API does not return — the contract is wrong and must be corrected before ingestion is written against it.

## Treasury Fiscal Data

| endpoint | status | rows | coverage | contract |
|---|---|---|---|---|
| `mspd_table_1` | **ERROR** | – | – | ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): M |
| `mspd_table_3_market` | **ERROR** | – | – | ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): M |
| `auctions_query` | **ERROR** | – | – | ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): M |
| `debt_to_penny` | **ERROR** | – | – | ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): M |
| `avg_interest_rates` | **ERROR** | – | – | ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): M |
| `interest_expense` | **ERROR** | – | – | ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): M |
| `operating_cash_balance` | **ERROR** | – | – | ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): M |
| `mts_table_1` | **ERROR** | – | – | ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): M |

### `mspd_table_1`

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): Max retries exceeded with url: /services/api/fiscal_service/v1/debt/mspd/mspd_table_1?page%5Bsize%5D=2&sort=-record_date (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`

### `mspd_table_3_market`

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): Max retries exceeded with url: /services/api/fiscal_service/v1/debt/mspd/mspd_table_3_market?page%5Bsize%5D=2&sort=-record_date (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`

Unresolved:

- Does this table expose maturity_date per CUSIP for the full history?
- Is TIPS outstanding reported at par or inflation-adjusted?
- Row count per month (drives storage strategy).

### `auctions_query`

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): Max retries exceeded with url: /services/api/fiscal_service/v1/accounting/od/auctions_query?page%5Bsize%5D=2&sort=-auction_date (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`

Unresolved:

- Are low_yield / median_yield published? (enables a real free tail proxy)
- Is allotment-at-high published?
- First date with primary dealer / direct / indirect breakdown.

### `debt_to_penny`

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): Max retries exceeded with url: /services/api/fiscal_service/v2/accounting/od/debt_to_penny?page%5Bsize%5D=2&sort=-record_date (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`

### `avg_interest_rates`

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): Max retries exceeded with url: /services/api/fiscal_service/v2/accounting/od/avg_interest_rates?page%5Bsize%5D=2&sort=-record_date (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`

### `interest_expense`

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): Max retries exceeded with url: /services/api/fiscal_service/v2/accounting/od/interest_expense?page%5Bsize%5D=2&sort=-record_date (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`

### `operating_cash_balance`

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): Max retries exceeded with url: /services/api/fiscal_service/v1/accounting/dts/operating_cash_balance?page%5Bsize%5D=2&sort=-record_date (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`

### `mts_table_1`

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='api.fiscaldata.treasury.gov', port=443): Max retries exceeded with url: /services/api/fiscal_service/v1/accounting/mts/mts_table_1?page%5Bsize%5D=2&sort=-record_date (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`

## FRED

Skipped: FRED_API_KEY not set in environment

## NY Fed ACM term premium

**Probe failed:** `ProxyError: HTTPSConnectionPool(host='www.newyorkfed.org', port=443): Max retries exceeded with url: /medialibrary/media/research/data_indicators/ACMTermPremium.xls (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))`
