# Source probe results

- Probe run (UTC): `2026-08-19T01:47:39.763188+00:00`

Field names below are **observed from live responses**. Anything marked MISSING means `config/sources.yaml` expected a field the API does not return — the contract is wrong and must be corrected before ingestion is written against it.

## Treasury Fiscal Data

| endpoint | status | rows | coverage | contract |
|---|---|---|---|---|
| `mspd_table_1` | ok | 4645 | 2001-01-31 → 2026-07-31 | OK |
| `mspd_table_3_market` | ok | 153404 | 2001-01-31 → 2026-07-31 | OK |
| `auctions_query` | ok | 11083 | 1979-10-31 → 2026-08-20 | OK |
| `debt_to_penny` | ok | 8373 | 1993-04-01 → 2026-08-17 | OK |
| `avg_interest_rates` | ok | 4993 | 2001-01-31 → 2026-07-31 | OK |
| `interest_expense` | ok | 7283 | 2010-05-31 → 2026-07-31 | OK |
| `operating_cash_balance` | ok | 16534 | 2005-10-03 → 2026-08-17 | OK |
| `mts_table_1` | ok | 3090 | 2015-03-31 → 2026-07-31 | OK |

### `mspd_table_1`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/mspd_table_1`

- Coverage: **2001-01-31 → 2026-07-31** (4645 rows)
- Observed fields (13): `debt_held_public_mil_amt`, `intragov_hold_mil_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `security_class_desc`, `security_type_desc`, `src_line_nbr`, `total_mil_amt`

- No field drift since the last probe.

### `mspd_table_3_market`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/mspd_table_3_market`

- Coverage: **2001-01-31 → 2026-07-31** (153404 rows)
- Observed fields (24): `inflation_adj_amt`, `interest_pay_date_1`, `interest_pay_date_2`, `interest_pay_date_3`, `interest_pay_date_4`, `interest_rate_pct`, `issue_date`, `issued_amt`, `maturity_date`, `outstanding_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `redeemed_amt`, `security_class1_desc`, `security_class2_desc`, `security_type_desc`, `series_cd`, `src_line_nbr`, `yield_pct`

- No field drift since the last probe.

### `auctions_query`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query`

- Coverage: **1979-10-31 → 2026-08-20** (11083 rows)
- Observed fields (114): `accrued_int_per100`, `accrued_int_per1000`, `adj_accrued_int_per1000`, `adj_price`, `allocation_pctage`, `allocation_pctage_decimals`, `announcemt_date`, `announcemtd_cusip`, `auction_date`, `auction_format`, `avg_med_discnt_margin`, `avg_med_discnt_rate`, `avg_med_investment_rate`, `avg_med_price`, `avg_med_yield`, `back_dated`, `back_dated_date`, `bid_to_cover_ratio`, `call_date`, `callable`, `called_date`, `cash_management_bill_cmb`, `closing_time_comp`, `closing_time_noncomp`, `comp_accepted`, `comp_bid_decimals`, `comp_tendered`, `comp_tenders_accepted`, `corpus_cusip`, `cpi_base_reference_period`, `currently_outstanding`, `cusip`, `dated_date`, `direct_bidder_accepted`, `direct_bidder_tendered`, `est_pub_held_mat_by_type_amt`, `fima_included`, `fima_noncomp_accepted`, `fima_noncomp_tendered`, `first_int_payment_date`, `first_int_period`, `floating_rate`, `frn_index_determination_date`, `frn_index_determination_rate`, `high_discnt_margin`, `high_discnt_rate`, `high_investment_rate`, `high_price`, `high_yield`, `index_ratio_on_issue_date`, `indirect_bidder_accepted`, `indirect_bidder_tendered`, `inflation_index_security`, `int_payment_frequency`, `int_rate`, `issue_date`, `low_discnt_margin`, `low_discnt_rate`, `low_investment_rate`, `low_price`, `low_yield`, `mat_date`, `maturity_date`, `max_comp_award`, `max_noncomp_award`, `max_single_bid`, `min_bid_amt`, `min_strip_amt`, `min_to_issue`, `multiples_to_bid`, `multiples_to_issue`, `nlp_exclusion_amt`, `nlp_reporting_threshold`, `noncomp_accepted`, `noncomp_tenders_accepted`, `offering_amt`, `original_cusip`, `original_dated_date`, `original_issue_date`, `original_security_term`, `pdf_filenm_announcemt`, `pdf_filenm_comp_results`, `pdf_filenm_noncomp_results`, `pdf_filenm_spec_announcemt`, `price_per100`, `primary_dealer_accepted`, `primary_dealer_tendered`, `record_date`, `ref_cpi_on_dated_date`, `ref_cpi_on_issue_date`, `reopening`, `security_term`, `security_term_day_month`, `security_term_week_year`, `security_type`, `series`, `soma_accepted`, `soma_holdings`, `soma_included`, `soma_tendered`, `spread`, `std_int_payment_per1000`, `strippable`, `tiin_conversion_factor_per1000`, `tint_cusip_1`, `tint_cusip_2`, `total_accepted`, `total_tendered`, `treas_retail_accepted`, `treas_retail_tenders_accepted`, `unadj_accrued_int_per1000`, `unadj_price`, `xml_filenm_announcemt`, `xml_filenm_comp_results`

- No field drift since the last probe.

- **Opportunistic fields FOUND:** `high_discnt_rate`, `low_discnt_rate`, `allocation_pctage`

- Opportunistic fields absent: `median_yield`

### `debt_to_penny`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny`

- Coverage: **1993-04-01 → 2026-08-17** (8373 rows)
- Observed fields (11): `debt_held_public_amt`, `intragov_hold_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`, `tot_pub_debt_out_amt`

- No field drift since the last probe.

### `avg_interest_rates`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates`

- Coverage: **2001-01-31 → 2026-07-31** (4993 rows)
- Observed fields (11): `avg_interest_rate_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `security_desc`, `security_type_desc`, `src_line_nbr`

- No field drift since the last probe.

### `interest_expense`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/interest_expense`

- Coverage: **2010-05-31 → 2026-07-31** (7283 rows)
- Observed fields (13): `expense_catg_desc`, `expense_group_desc`, `expense_type_desc`, `fytd_expense_amt`, `month_expense_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`

- No field drift since the last probe.

### `operating_cash_balance`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance`

- Coverage: **2005-10-03 → 2026-08-17** (16534 rows)
- Observed fields (16): `account_type`, `close_today_bal`, `open_fiscal_year_bal`, `open_month_bal`, `open_today_bal`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`, `sub_table_name`, `table_nbr`, `table_nm`

- No field drift since the last probe.

### `mts_table_1`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_1`

- Coverage: **2015-03-31 → 2026-07-31** (3090 rows)
- Observed fields (21): `classification_desc`, `classification_id`, `current_month_dfct_sur_amt`, `current_month_gross_outly_amt`, `current_month_gross_rcpt_amt`, `data_type_cd`, `line_code_nbr`, `parent_id`, `print_order_nbr`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `record_type_cd`, `sequence_level_nbr`, `sequence_number_cd`, `src_line_nbr`, `table_nbr`

- No field drift since the last probe.

## FRED

| series | status | freq | units | coverage | last updated |
|---|---|---|---|---|---|
| `DGS3MO` | ok | D | % | 1981-09-01 → 2026-08-17 | 2026-08-18 15:16:26-05 |
| `DGS6MO` | ok | D | % | 1981-09-01 → 2026-08-17 | 2026-08-18 15:16:26-05 |
| `DGS1` | ok | D | % | 1962-01-02 → 2026-08-17 | 2026-08-18 15:16:24-05 |
| `DGS2` | ok | D | % | 1976-06-01 → 2026-08-17 | 2026-08-18 15:16:22-05 |
| `DGS5` | ok | D | % | 1962-01-02 → 2026-08-17 | 2026-08-18 15:16:25-05 |
| `DGS10` | ok | D | % | 1962-01-02 → 2026-08-17 | 2026-08-18 15:16:25-05 |
| `DGS20` | ok | D | % | 1962-01-02 → 2026-08-17 | 2026-08-18 15:16:22-05 |
| `DGS30` | ok | D | % | 1977-02-15 → 2026-08-17 | 2026-08-18 15:16:23-05 |
| `WALCL` | ok | W | Mil. of U.S. $ | 2002-12-18 → 2026-08-12 | 2026-08-13 15:32:11-05 |
| `WRESBAL` | ok | W | Mil. of U.S. $ | 2002-12-18 → 2026-08-12 | 2026-08-13 15:31:43-05 |
| `RRPONTSYD` | ok | D | Bil. of US $ | 2003-02-07 → 2026-08-18 | 2026-08-18 13:02:26-05 |
| `WTREGEN` | ok | W | Mil. of U.S. $ | 2002-12-18 → 2026-08-12 | 2026-08-13 15:31:31-05 |
| `SOFR` | ok | D | % | 2018-04-03 → 2026-08-17 | 2026-08-18 07:02:21-05 |
| `EFFR` | ok | D | % | 2000-07-03 → 2026-08-17 | 2026-08-18 08:02:19-05 |
| `MMMFFAQ027S` | ok | Q | Mil. of U.S. $ | 1945-10-01 → 2026-01-01 | 2026-06-11 21:15:44-05 |
| `GFDEBTN` | ok | Q | Mil. of $ | 1966-01-01 → 2026-01-01 | 2026-06-18 14:30:20-05 |
| `FYFSGDA188S` | ok | A | % of GDP | 1929-01-01 → 2025-01-01 | 2026-04-09 08:07:35-05 |
| `A091RC1Q027SBEA` | ok | Q | Bil. of $ | 1947-01-01 → 2026-04-01 | 2026-07-30 10:09:18-05 |
| `FGRECPT` | ok | Q | Bil. of $ | 1947-01-01 → 2026-01-01 | 2026-06-25 07:51:13-05 |
| `GDP` | ok | Q | Bil. of $ | 1947-01-01 → 2026-04-01 | 2026-07-30 10:07:52-05 |
| `THREEFYTP10` | ok | D | % | 1990-01-02 → 2026-08-14 | 2026-08-18 14:04:21-05 |

## NY Fed ACM term premium

- URL: `https://www.newyorkfed.org/medialibrary/media/research/data_indicators/ACMTermPremium.xls`
- Content-Type: `application/vnd.ms-excel`, 10134528 bytes
- Parsed with: `xlrd`
- Rows: 782
- Columns: `DATE`, `ACMY01`, `ACMY02`, `ACMY03`, `ACMY04`, `ACMY05`, `ACMY06`, `ACMY07`, `ACMY08`, `ACMY09`, `ACMY10`, `ACMTP01`, `ACMTP02`, `ACMTP03`, `ACMTP04`, `ACMTP05`, `ACMTP06`, `ACMTP07`, `ACMTP08`, `ACMTP09`, `ACMTP10`, `ACMRNY01`, `ACMRNY02`, `ACMRNY03`, `ACMRNY04`, `ACMRNY05`, `ACMRNY06`, `ACMRNY07`, `ACMRNY08`, `ACMRNY09`, `ACMRNY10`
- Series of interest present: `ACMTP02`, `ACMTP05`, `ACMTP10`
