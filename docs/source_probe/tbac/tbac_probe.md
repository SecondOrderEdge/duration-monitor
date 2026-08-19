# TBAC bill share band probe

**Claim under test:** `reference_levels.bill_share_recommended_band == [0.15, 0.20]`

**Outcome: OTHER RANGES FOUND** — Ranges near bill mentions were found, but none was 15-20%. If these are the committee's actual language, the configured band is wrong.

`NOT FOUND` means the record was searched and the statement is absent.
`NOT REACHED` means the search did not happen. They are not the same finding.

## Coverage

Documents that yielded text, by year. **Read the verdict against this.** The claim is that TBAC has *long* referenced the band, so a `NOT FOUND` spanning a couple of years does not answer it.

| year | documents searched |
|---|---|
| 2002 | 2 |
| 2003 | 7 |
| 2004 | 8 |
| 2005 | 8 |
| 2006 | 8 |
| 2007 | 8 |
| 2008 | 7 |
| 2009 | 8 |
| 2010 | 2 |
| 2021 | 1 |
| 2023 | 1 |
| 2026 | 16 |

## Entry points

| url | fetched | status | documents | indexes |
|---|---|---|---|---|
| `https://home.treasury.gov/policy-issues/financing-the-government/quart` | yes | 200 | 0 | 2 |
| `https://home.treasury.gov/policy-issues/financing-the-government/quart` | yes | 200 | 0 | 8 |
| `https://home.treasury.gov/policy-issues/financing-the-government/treas` | no | 404 | 0 | 0 |
| `https://home.treasury.gov/policy-issues/financing-the-government/quart` | yes | 200 | 16 | 2 |

## Documents examined

| document | characters | note |
|---|---|---|
| Financing Estimates: 2026 - 3rd Quarter | 12,833 |  |
| Economic Policy Statements to TBAC: 2026 - 3rd Quarter​ | 31,486 |  |
| Policy Statement: 2026 - 3rd Quarter | 14,801 |  |
| TBAC Report to Secretary: 2026 - 3rd Quarter | 20,980 |  |
| TBAC Minutes: 2026 - 3rd Quarter | 22,111 |  |
| TBAC Recommended Financing Table by Refunding Quarter | 999 |  |
| Treasury Presentation to TBAC (Final): 2026 - 3rd Quarter | 55,807 |  |
| TBAC Presentation to Treasury: (Charge 1 | 26,928 |  |
| Charge 2 | 28,274 |  |
| Archives | 111,011 |  |
| Auction Schedule: XML Format | 10,916 |  |
| Auction Schedule: PDF Format | 21,096 |  |
| Buyback Schedule: XML Format | 2,528 |  |
| Buyback Schedule: PDF Format | 3,120 |  |
| Primary Dealer Meeting Agenda: 2026 - 3rd Quarter | 7,122 |  |
| Quarterly Release Data: 2026 - 3rd Quarter | 126,910 |  |
| Letter dated May 9, 2023 from Former TBAC Chairs and Vice Chairs on Ra | 5,617 |  |
| Letter dated September 21, 2021 from TBAC Chair Beth Hammack and Vice  | 4,332 |  |
| Letter dated May 2, 2016 from Outgoing TBAC Member Matthew E. Zames on | 0 | no extractable text (likely a scanned image PDF) |
| Letter dated April 25, 2011 from TBAC Chairman Matthew E. Zames on Rai | 0 | no extractable text (likely a scanned image PDF) |
| Q1 | 13,526 |  |
| Data | 43,107 |  |
| Q1 | 14,853 |  |
| Data | 25,989 |  |
| Q2 | 15,074 |  |
| Data | 27,491 |  |
| Q3 | 14,539 |  |
| Data | 15,662 |  |
| Q4 | 14,594 |  |
| Data | 15,893 |  |
| Q1 | 11,397 |  |
| Data | 27,284 |  |
| Q2 | 13,417 |  |
| Data | 17,400 |  |
| Data | 27,261 |  |
| Q4 | 12,874 |  |
| Data | 25,082 |  |
| Q1 | 8,761 |  |
| Data | 25,011 |  |
| Q2 | 9,194 |  |
| Data | 25,927 |  |
| Q3 | 9,193 |  |
| Data | 27,005 |  |
| Q4 | 10,257 |  |
| Data | 26,209 |  |
| Q1 | 11,231 |  |
| Data | 46,033 |  |
| Q2 | 13,188 |  |
| Data | 40,075 |  |
| Q3 | 12,678 |  |
| Data | 36,915 |  |
| Q4 | 11,229 |  |
| Data | 34,018 |  |
| Q1 | 12,213 |  |
| Data | 34,902 |  |
| Q2 | 13,150 |  |
| Data | 57,597 |  |
| Q3 | 12,158 |  |
| Data | 46,611 |  |
| Q4 | 12,472 |  |
| Data | 48,001 |  |
| Q1 | 7,200 |  |
| Data | 59,274 |  |
| Q2 | 5,271 |  |
| Data | 24,676 |  |
| Q3 | 7,211 |  |
| Data | 64,043 |  |
| Q4 | 5,546 |  |
| Data | 23,299 |  |
| Q1 | 9,917 |  |
| Data | 57,078 |  |
| Q2 | 5,469 |  |
| Data | 16,867 |  |
| Data | 51,837 |  |
| Q4 | 4,915 |  |
| Data | 22,030 |  |
| Q1 | 7,308 |  |
| Data | 15,329 |  |

## Passages found

### Q1

<https://home.treasury.gov/system/files/276/Monday-chart-template-Feb-2010-Final.pdf>

- range `[8, 70]`

  > 5.7 -7.8 -15.1 -17.6 -11.9 -9.1 -9.3 -20.3 -5.2 25 -20 -15 -10 -5 25 -20 -15 -10 -5 P a y d o w n • Treasury has reduced 30% 90% 100% Percentage Breakdown of Quarterly Marketable Issuance Fiscal Year -25-25 I 05 II III IV I 06 II III IV I 07 II III IV I 08 II III IV I 09 II III IV I 10 Treasury has reduced reliance on bill financing over the past calendar year, moving from 84% in December 2008 to 70% in 15% 20% 25% 40% 50% 60% 70% 80% 90% Bills followleft ‐side scale. Coupons followright ‐side scale. December 2009. 0% 5% 10% 0% 10% 20% 30% 40% 1981 1983 1985 1987 1989 1991 1993 1995 1997 1999 2001 2003 2005 2007 2009 Office of Debt Management 5 Bills 2-3 yrs 4-7 yrs 8-10 yrs Bonds TIPS Note: Previous releases of Q

### Q4

<https://home.treasury.gov/system/files/276/2009-q4-chart.pdf>

- range `[20, 10]`

  > rrowing estimates by primary dealersscenarios given the wide range of borrowing estimates by primary dealers for FY 2010. Office of Debt Management 10 30% 40% Rolling 12-Month Growth Rates Corp Taxes WH Taxes nWH Taxes • Withheld taxes, comprising nearly 79% of revenues, continue to decline. 0% 10% 20% ae s -40% -30% -20% -10% -50% Mar-82 Mar-83 Mar-84 Mar-85 Mar-86 Mar-87 Mar-88 Mar-89 Mar-90 Mar-91 Mar-92 Mar-93 Mar-94 Mar-95 Mar-96 Mar-97 Mar-98 Mar-99 Mar-00 Mar-01 Mar-02 Mar-03 Mar-04 Mar-05 Mar-06 Mar-07 Mar-08 Mar-09 Central Dealer Estimates For Coupon and 52-Wk Bill Auctions Over the Next 3 Months Pi d l 30 35 40 45 50 ns Avg of High Est • Primary dealers estimate that marginal and gradual increases in coupon sizes can address additional borrowing needs 5 10 15 20 25 30 $ Billion Avg of Central Est Avg of Low Est Office of Debt Management 11 borrowing needs. 5 52-wk Nov 52-wk Dec

### Q3

<https://home.treasury.gov/system/files/276/2005-q3-charts.pdf>

- range `[4, 2]`

  > IV I 04 II III IV I 05 II $billions -15 -10 -5 0 5 10 15 20 25 30 $ billions State and Local Govt. Series Savings Bonds Foreign Series 6 • Percentage changes in auction sizes are equally distributed across auctioned securities to meet financing needs. Projected Net Marketable Borrowing and Hypothetical Auction Sizes -4% -2% 0% 2% 4% 6% 8% 10% 12% 14% 2005 2006 2007 2008 2009 2010 Percent 50 100 150 200 250 300 350 400$ Billions Net Marketable Borrowing (RHS) Projections are based on current OMB MSR budget estimates (except internal Treasury estimate for FY2005). Future residual financing needs are spread equally across auctioned securities to maintain constant maturity of issuance. Bars represent percentage change in average auction size

### Q1

<https://home.treasury.gov/system/files/276/2004-q1-charts.pdf>

- range `[4, 8]`

  > ther Mortgages Consumer Credit Other February 2, 2004-7 DOMESTIC NONFINANCIAL CREDIT MARKET AND TREASURY DEBT $Bil. $Bil. Source: U.S. Federal Reserve Board of Governors Flow of Funds. 30 20 10 0 PercentPercent 30 20 10 0 Department of the Treasury Office of Debt Management 1969 1973 1977 1981 1985 1989 1993 1997 2001 TREASURY BILLS AS A PERCENTAGE OF THE MONEY MARKET Quarterly Department of the Treasury Office of Debt ManagementFebruary 2, 2004-8 Percent Percent 1 1Money market = Treasury bills, nonfinancial commercial paper, and financial open market paper. 25 30 35 40 45 50 55 60 65 70 25 30 35 40 45 50 55 60 65 70 Source: U.S. Federal Reserve Board of Governors Flow of Funds statistical release Z.1. 0 50 100 150 200 250 300 350 400 450 0 50 100 150 200 250 300 350

### Q3

<https://home.treasury.gov/system/files/276/2004-q3-charts.pdf>

- range `[4, 8]`

  > Other Mortgages Consumer Credit Other August 2, 2004-7 DOMESTIC NONFINANCIAL CREDIT MARKET AND TREASURY DEBT $Bil.$Bil. Source: U.S. Federal Reserve Board of Governors Flow of Funds. 30 20 10 0 Percent Percent 30 20 10 0 Department of the Treasury Office of Debt Management 1969 1973 1977 1981 1985 1989 1993 1997 2001 TREASURY BILLS AS A PERCENTAGE OF THE MONEY MARKET Quarterly Department of the Treasury Office of Debt Management August 2, 2004-8 PercentPercent 1 1 Money market = Treasury bills, nonfinancial commercial paper, and financial open market paper. 25 30 35 40 45 50 55 60 65 70 25 30 35 40 45 50 55 60 65 70 Source: U.S. Federal Reserve Board of Governors Flow of Funds statistical release Z.1. 0 50 100 150 200 250 300 350 400 450 0 50 100 150 200 250 300 350

### Q1

<https://home.treasury.gov/system/files/276/2003-Feb.pdf>

- range `[3, 5]`

  > and stable Treasuries Muni's Corporates Home Mortgages Consumer Credit Other Department of the Treasury Office of Market Finance February 3, 2003-4 Domestic Nonfinancial Credit Market and Treasury Debt Source: U.S. Federal Reserve Board of Governors Flow of Funds. Quarterly 1969 1973 1977 1981 1985 1989 1993 1997 2001 Treasury Bills as a Percentage of the Money Market Quarterly Department of the Treasury Office of Market Finance February 3, 2003-5 PercentPercent 1 25 30 35 40 45 50 55 60 65 70 25 30 35 40 45 50 55 60 65 70 Treasury's share of money markets near historic lows Source: U.S. Federal Reserve Board of Governors Flow of Funds statistical release Z.1. 1 Money market = Treasury bills, nonfinancial commercial paper and bankers acceptances. 0 50 100 150 200 250 3

