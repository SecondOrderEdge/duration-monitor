# Source probe results

- Probe run (UTC): `2026-08-17T14:31:29.390744+00:00`

Field names below are **observed from live responses**. Anything marked MISSING means `config/sources.yaml` expected a field the API does not return — the contract is wrong and must be corrected before ingestion is written against it.

## Treasury Fiscal Data

| endpoint | status | rows | coverage | contract |
|---|---|---|---|---|
| `mspd_table_1` | ok | 4645 | 2001-01-31 → 2026-07-31 | OK |
| `mspd_table_3_market` | ok | 153404 | 2001-01-31 → 2026-07-31 | **1 MISSING** |
| `auctions_query` | ok | 11080 | 1979-10-31 → 2026-08-20 | OK |
| `debt_to_penny` | ok | 8371 | 1993-04-01 → 2026-08-13 | OK |
| `avg_interest_rates` | ok | 4993 | 2001-01-31 → 2026-07-31 | OK |
| `interest_expense` | ok | 7283 | 2010-05-31 → 2026-07-31 | OK |
| `operating_cash_balance` | ok | 16526 | 2005-10-03 → 2026-08-13 | OK |
| `mts_table_1` | ok | 3090 | 2015-03-31 → 2026-07-31 | **2 MISSING** |

### `mspd_table_1`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/mspd_table_1`

- Coverage: **2001-01-31 → 2026-07-31** (4645 rows)
- Observed fields (13): `debt_held_public_mil_amt`, `intragov_hold_mil_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `security_class_desc`, `security_type_desc`, `src_line_nbr`, `total_mil_amt`

- Unexpected (returned, not in contract): `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`

### `mspd_table_3_market`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/mspd_table_3_market`

- Coverage: **2001-01-31 → 2026-07-31** (153404 rows)
- Observed fields (24): `inflation_adj_amt`, `interest_pay_date_1`, `interest_pay_date_2`, `interest_pay_date_3`, `interest_pay_date_4`, `interest_rate_pct`, `issue_date`, `issued_amt`, `maturity_date`, `outstanding_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `redeemed_amt`, `security_class1_desc`, `security_class2_desc`, `security_type_desc`, `series_cd`, `src_line_nbr`, `yield_pct`

- **MISSING (expected, not returned):** `cusip`

- Unexpected (returned, not in contract): `inflation_adj_amt`, `interest_pay_date_1`, `interest_pay_date_2`, `interest_pay_date_3`, `interest_pay_date_4`, `issued_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_fiscal_quarter`, `record_fiscal_year`, `redeemed_amt`, `security_type_desc`, `series_cd`, `src_line_nbr`

Open questions this probe was meant to answer:

- Does this table expose maturity_date per CUSIP for the full history?
- Is TIPS outstanding reported at par or inflation-adjusted?
- Row count per month (drives storage strategy).

### `auctions_query`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query`

- Coverage: **1979-10-31 → 2026-08-20** (11080 rows)
- Observed fields (114): `accrued_int_per100`, `accrued_int_per1000`, `adj_accrued_int_per1000`, `adj_price`, `allocation_pctage`, `allocation_pctage_decimals`, `announcemt_date`, `announcemtd_cusip`, `auction_date`, `auction_format`, `avg_med_discnt_margin`, `avg_med_discnt_rate`, `avg_med_investment_rate`, `avg_med_price`, `avg_med_yield`, `back_dated`, `back_dated_date`, `bid_to_cover_ratio`, `call_date`, `callable`, `called_date`, `cash_management_bill_cmb`, `closing_time_comp`, `closing_time_noncomp`, `comp_accepted`, `comp_bid_decimals`, `comp_tendered`, `comp_tenders_accepted`, `corpus_cusip`, `cpi_base_reference_period`, `currently_outstanding`, `cusip`, `dated_date`, `direct_bidder_accepted`, `direct_bidder_tendered`, `est_pub_held_mat_by_type_amt`, `fima_included`, `fima_noncomp_accepted`, `fima_noncomp_tendered`, `first_int_payment_date`, `first_int_period`, `floating_rate`, `frn_index_determination_date`, `frn_index_determination_rate`, `high_discnt_margin`, `high_discnt_rate`, `high_investment_rate`, `high_price`, `high_yield`, `index_ratio_on_issue_date`, `indirect_bidder_accepted`, `indirect_bidder_tendered`, `inflation_index_security`, `int_payment_frequency`, `int_rate`, `issue_date`, `low_discnt_margin`, `low_discnt_rate`, `low_investment_rate`, `low_price`, `low_yield`, `mat_date`, `maturity_date`, `max_comp_award`, `max_noncomp_award`, `max_single_bid`, `min_bid_amt`, `min_strip_amt`, `min_to_issue`, `multiples_to_bid`, `multiples_to_issue`, `nlp_exclusion_amt`, `nlp_reporting_threshold`, `noncomp_accepted`, `noncomp_tenders_accepted`, `offering_amt`, `original_cusip`, `original_dated_date`, `original_issue_date`, `original_security_term`, `pdf_filenm_announcemt`, `pdf_filenm_comp_results`, `pdf_filenm_noncomp_results`, `pdf_filenm_spec_announcemt`, `price_per100`, `primary_dealer_accepted`, `primary_dealer_tendered`, `record_date`, `ref_cpi_on_dated_date`, `ref_cpi_on_issue_date`, `reopening`, `security_term`, `security_term_day_month`, `security_term_week_year`, `security_type`, `series`, `soma_accepted`, `soma_holdings`, `soma_included`, `soma_tendered`, `spread`, `std_int_payment_per1000`, `strippable`, `tiin_conversion_factor_per1000`, `tint_cusip_1`, `tint_cusip_2`, `total_accepted`, `total_tendered`, `treas_retail_accepted`, `treas_retail_tenders_accepted`, `unadj_accrued_int_per1000`, `unadj_price`, `xml_filenm_announcemt`, `xml_filenm_comp_results`

- Unexpected (returned, not in contract): `accrued_int_per100`, `accrued_int_per1000`, `adj_accrued_int_per1000`, `adj_price`, `allocation_pctage`, `allocation_pctage_decimals`, `announcemt_date`, `announcemtd_cusip`, `auction_format`, `avg_med_discnt_margin`, `avg_med_discnt_rate`, `avg_med_investment_rate`, `avg_med_price`, `avg_med_yield`, `back_dated`, `back_dated_date`, `call_date`, `callable`, `called_date`, `cash_management_bill_cmb`, `closing_time_comp`, `closing_time_noncomp`, `comp_accepted`, `comp_bid_decimals`, `comp_tendered`, `comp_tenders_accepted`, `corpus_cusip`, `cpi_base_reference_period`, `currently_outstanding`, `dated_date`, `direct_bidder_tendered`, `est_pub_held_mat_by_type_amt`, `fima_included`, `fima_noncomp_accepted`, `fima_noncomp_tendered`, `first_int_payment_date`, `first_int_period`, `floating_rate`, `frn_index_determination_date`, `frn_index_determination_rate`, `high_discnt_margin`, `high_discnt_rate`, `high_investment_rate`, `high_price`, `index_ratio_on_issue_date`, `indirect_bidder_tendered`, `inflation_index_security`, `int_payment_frequency`, `int_rate`, `low_discnt_margin`, `low_discnt_rate`, `low_investment_rate`, `low_price`, `low_yield`, `mat_date`, `max_comp_award`, `max_noncomp_award`, `max_single_bid`, `min_bid_amt`, `min_strip_amt`, `min_to_issue`, `multiples_to_bid`, `multiples_to_issue`, `nlp_exclusion_amt`, `nlp_reporting_threshold`, `noncomp_accepted`, `noncomp_tenders_accepted`, `original_cusip`, `original_dated_date`, `original_issue_date`, `original_security_term`, `pdf_filenm_announcemt`, `pdf_filenm_comp_results`, `pdf_filenm_noncomp_results`, `pdf_filenm_spec_announcemt`, `price_per100`, `primary_dealer_tendered`, `record_date`, `ref_cpi_on_dated_date`, `ref_cpi_on_issue_date`, `reopening`, `security_term_day_month`, `security_term_week_year`, `series`, `soma_accepted`, `soma_holdings`, `soma_included`, `soma_tendered`, `spread`, `std_int_payment_per1000`, `strippable`, `tiin_conversion_factor_per1000`, `tint_cusip_1`, `tint_cusip_2`, `total_tendered`, `treas_retail_accepted`, `treas_retail_tenders_accepted`, `unadj_accrued_int_per1000`, `unadj_price`, `xml_filenm_announcemt`, `xml_filenm_comp_results`

- **Opportunistic fields FOUND:** `low_yield`, `high_discnt_rate`, `allocation_pctage`

- Opportunistic fields absent: `median_yield`

Open questions this probe was meant to answer:

- Are low_yield / median_yield published? (enables a real free tail proxy)
- Is allotment-at-high published?
- First date with primary dealer / direct / indirect breakdown.

### `debt_to_penny`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny`

- Coverage: **1993-04-01 → 2026-08-13** (8371 rows)
- Observed fields (11): `debt_held_public_amt`, `intragov_hold_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`, `tot_pub_debt_out_amt`

- Unexpected (returned, not in contract): `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`

### `avg_interest_rates`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates`

- Coverage: **2001-01-31 → 2026-07-31** (4993 rows)
- Observed fields (11): `avg_interest_rate_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `security_desc`, `security_type_desc`, `src_line_nbr`

- Unexpected (returned, not in contract): `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`

### `interest_expense`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/interest_expense`

- Coverage: **2010-05-31 → 2026-07-31** (7283 rows)
- Observed fields (13): `expense_catg_desc`, `expense_group_desc`, `expense_type_desc`, `fytd_expense_amt`, `month_expense_amt`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`

- Unexpected (returned, not in contract): `expense_catg_desc`, `expense_group_desc`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`

### `operating_cash_balance`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance`

- Coverage: **2005-10-03 → 2026-08-13** (16526 rows)
- Observed fields (16): `account_type`, `close_today_bal`, `open_fiscal_year_bal`, `open_month_bal`, `open_today_bal`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`, `sub_table_name`, `table_nbr`, `table_nm`

- Unexpected (returned, not in contract): `open_fiscal_year_bal`, `open_month_bal`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_fiscal_quarter`, `record_fiscal_year`, `src_line_nbr`, `sub_table_name`, `table_nbr`, `table_nm`

### `mts_table_1`

`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_1`

- Coverage: **2015-03-31 → 2026-07-31** (3090 rows)
- Observed fields (21): `classification_desc`, `classification_id`, `current_month_dfct_sur_amt`, `current_month_gross_outly_amt`, `current_month_gross_rcpt_amt`, `data_type_cd`, `line_code_nbr`, `parent_id`, `print_order_nbr`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_date`, `record_fiscal_quarter`, `record_fiscal_year`, `record_type_cd`, `sequence_level_nbr`, `sequence_number_cd`, `src_line_nbr`, `table_nbr`

- **MISSING (expected, not returned):** `current_fytd_budget_amt`, `current_month_budget_amt`

- Unexpected (returned, not in contract): `classification_id`, `current_month_dfct_sur_amt`, `current_month_gross_outly_amt`, `current_month_gross_rcpt_amt`, `data_type_cd`, `line_code_nbr`, `parent_id`, `print_order_nbr`, `record_calendar_day`, `record_calendar_month`, `record_calendar_quarter`, `record_calendar_year`, `record_fiscal_quarter`, `record_fiscal_year`, `record_type_cd`, `sequence_level_nbr`, `sequence_number_cd`, `src_line_nbr`, `table_nbr`

## FRED

Skipped: FRED_API_KEY not set in environment

## NY Fed ACM term premium

- URL: `https://www.newyorkfed.org/medialibrary/media/research/data_indicators/ACMTermPremium.xls`
- Content-Type: `application/vnd.ms-excel`, 10133504 bytes
- Parsed with: `xlrd`
- Rows: 782
- Columns: `DATE`, `ACMY01`, `ACMY02`, `ACMY03`, `ACMY04`, `ACMY05`, `ACMY06`, `ACMY07`, `ACMY08`, `ACMY09`, `ACMY10`, `ACMTP01`, `ACMTP02`, `ACMTP03`, `ACMTP04`, `ACMTP05`, `ACMTP06`, `ACMTP07`, `ACMTP08`, `ACMTP09`, `ACMTP10`, `ACMRNY01`, `ACMRNY02`, `ACMRNY03`, `ACMRNY04`, `ACMRNY05`, `ACMRNY06`, `ACMRNY07`, `ACMRNY08`, `ACMRNY09`, `ACMRNY10`
- Series of interest present: `ACMTP02`, `ACMTP05`, `ACMTP10`
