# TBAC bill share band probe

**Claim under test:** `reference_levels.bill_share_recommended_band == [0.15, 0.20]`

**Outcome: EVIDENCE FOUND** — 20 passage(s) state a 15-20% range near a mention of bills. Read the context before setting verified: a range appearing in a document is not the same as the committee recommending it.

`NOT FOUND` means the record was searched and the statement is absent.
`NOT REACHED` means the search did not happen. They are not the same finding.

## Coverage

Documents that yielded text, by year. **Read the verdict against this.** The claim is that TBAC has *long* referenced the band, so a `NOT FOUND` spanning a couple of years does not answer it.

| year | documents searched |
|---|---|
| 1922 | 1 |
| 2026 | 5 |
| 2063 | 1 |
| unknown | 73 |

By document class. The claim is a sentence, so the classes that matter are minutes and reports; a run heavy in chart decks has searched a lot and looked in the wrong place.

| class | documents searched |
|---|---|
| minutes | 1 |
| press release | 77 |
| report | 2 |

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
| TBAC Minutes: 2026 - 3rd Quarter | 22,111 |  |
| TBAC Report to Secretary: 2026 - 3rd Quarter | 20,980 |  |
| 2nd Quarter​ | 22,715 |  |
| Financing Estimates: 2026 - 3rd Quarter | 12,833 |  |
| Economic Policy Statements to TBAC: 2026 - 3rd Quarter​ | 31,486 |  |
| Policy Statement: 2026 - 3rd Quarter | 14,801 |  |
| 2nd Quarter | 20,692 |  |
| 1st Quarter | 23,367 |  |
| 4th Quarter​​ | 19,429 |  |
| 3rd Quarter​ | 21,229 |  |
| 2nd Quarter | 25,290 |  |
| 1st Quarter | 21,197 |  |
| 4th Quarter​​ | 20,620 |  |
| 3rd Quarter​ | 23,256 |  |
| 2nd Quarter | 22,770 |  |
| 1st Quarter | 26,011 |  |
| 4th Quarter​​ | 24,231 |  |
| 3rd Quarter​ | 23,772 |  |
| 2nd Quarter | 22,911 |  |
| 1st Quarter | 21,175 |  |
| 4th Quarter​​ | 20,345 |  |
| 3rd Quarter​ | 21,435 |  |
| 2nd Quarter | 18,936 |  |
| 1st Quarter | 19,250 |  |
| 4th Quarter | 21,328 |  |
| 3rd Quarter​ | 23,349 |  |
| 2nd Quarter | 23,161 |  |
| 1st Quarter | 25,885 |  |
| 4th Quarter​​ | 24,650 |  |
| 3rd Quarter​ | 24,948 |  |
| 2nd Quarter | 22,275 |  |
| 1st Quarter | 23,570 |  |
| 4th Quarter​ | 22,776 |  |
| 3rd Quarter | 24,514 |  |
| 2nd Quarter | 25,021 |  |
| 1st Quarter | 22,605 |  |
| 4th Quarter | 24,280 |  |
| 3rd Quarter | 22,990 |  |
| 2nd Quarter | 23,124 |  |
| 1st Quarter | 22,452 |  |
| 4th Quarter | 26,225 |  |
| 3rd Quarter | 25,170 |  |
| 2nd Quarter​ | 29,112 |  |
| 1st Quarter | 23,979 |  |
| 4th Quarter | 29,189 |  |
| 3rd Quarter | 21,204 |  |
| 1st Quarter | 21,299 |  |
| 4th Quarter | 20,573 |  |
| 3rd Quarter | 23,006 |  |
| 2nd Quarter | 24,248 |  |
| 1st Quarter | 22,387 |  |
| 4th Quarter | 20,374 |  |
| 3rd Quarter | 22,480 |  |
| 2nd Quarter | 22,205 |  |
| 1st Quarter | 20,572 |  |
| 4th Quarter | 21,120 |  |
| 3rd Quarter | 21,645 |  |
| 2nd Quarter | 19,208 |  |
| 1st Quarter | 19,373 |  |
| 4th Quarter | 17,935 |  |
| 3rd Quarter | 20,722 |  |
| 2nd Quarter | 19,520 |  |
| 1st Quarter | 18,426 |  |
| 4th Quarter | 18,824 |  |
| 3rd Quarter | 19,421 |  |
| 2nd Quarter | 19,249 |  |
| 1st Quarter | 17,472 |  |
| 4th Quarter | 20,049 |  |
| 3rd Quarter | 19,328 |  |
| 2nd Quarter | 18,163 |  |
| 1st Quarter | 18,563 |  |
| 4th Quarter | 15,896 |  |
| 3rd Quarter | 23,578 |  |
| 2nd Quarter | 25,015 |  |
| 1st Quarter | 26,721 |  |
| 4th Quarter | 22,335 |  |
| 3rd Quarter | 23,674 |  |
| 2nd Quarter | 22,619 |  |
| 1st Quarter | 20,478 |  |
| 4th Quarter | 21,754 |  |

## Passages found

### 3rd Quarter​

<https://home.treasury.gov/news/press-releases/jy2513>

- range `[30, 35]`

  > e issuance of securities, market structure and investor demand, and debt maturity distribution. First and foremost, the Committee felt that T-bill issuance should continue to act as a shock absorber, allowing coupons to be issued in a regular and predictable manner. Historically, this has necessitated operating with a T-bill share as high as 30-35% for short periods. In order to re-examine considerations for T-bill issuance over the medium and long term, the presenting members used the Optimal Debt Model to more closely review the trade-off between average interest costs and volatility in deficit financing. Within the context of the model, on balance, T-bills pr

### 2nd Quarter

<https://home.treasury.gov/news/press-releases/jy2316>

- range `[15, 20]` **← matches the configured band**

  > oth could be explored in the pursuit of supporting market liquidity, but further study would be needed. In terms of issuance, the Committee recommended that Treasury keep nominal auction sizes unchanged for this quarter. Turning to TIPS, the Committee supported increasing the 5y and 10y TIPS auction by $1bn. While the T-bill share would be expected to remain slightly above the current 15 to 20% recommended T-bill range, on balance, the Committee felt this would best achieve Treasury’s objective of minimizing cost to the taxpayer by operating in a regular and predictable framework. The Committee supported a return to the 15-20% range in the medium term, noting this may happen without further coupon increases.

### 4th Quarter​​

<https://home.treasury.gov/news/press-releases/jy1865>

- range `[15, 20]` **← matches the configured band**

  > thin Treasury’s regular and predictable framework. The charge suggested Treasury consider skewing increases in issuance towards tenors which have less sensitivity to term premium increases, and ones that benefit from greater liquidity. The Committee supported meaningful deviation from the historical recommendation for 15-20% T-Bill share. While most members supported a return to within the recommended band over time, the Committee noted that the work Treasury has done to meaningfully increase WAM over the past 15 years affords them increased flexibility with T-Bill share in the medium term. The Committee then discussed the composition of coupon

### 1st Quarter

<https://home.treasury.gov/news/press-releases/jy1239>

- range `[15, 20]` **← matches the configured band**

  > allow Treasury to meet its financing needs in an efficient manner while maintaining flexibility to accommodate further meaningful financing needs should they arise. Over a longer horizon, this issuance path is expected to: keep the average maturity of Treasury debt and its average duration roughly unchanged; leave the T-bill share of outstanding debt within the recommended 15% to 20% range; and gradually increase or maintain the share of TIPS in outstanding debt. Of course, given the considerable uncertainty surrounding the economy and projected borrowing needs, Treasury will need to retain flexibility in its approach. Respectfully, _______________________________ Beth Hammack Chair, Treasury Borr

### 4th Quarter​​

<https://home.treasury.gov/news/press-releases/jy1073>

- range `[15, 20]` **← matches the configured band**

  > allow Treasury to meet its financing needs in an efficient manner while maintaining flexibility to accommodate further meaningful financing needs should they arise. Over a longer horizon, this issuance path is expected to: keep the average maturity of Treasury debt and its average duration roughly unchanged; leave the T-bill share of outstanding debt within the recommended 15% to 20% range; and gradually increase the share of TIPS in outstanding debt. Of course, given the considerable uncertainty surrounding the economy and projected borrowing needs, Treasury will need to retain flexibility in its approach. Respectfully, _______________________________ Beth Hammack Chair, Treasury Borrowing Adviso

### 3rd Quarter​

<https://home.treasury.gov/news/press-releases/jy0909>

- range `[15, 20]` **← matches the configured band**

  > er in both new issues and reopenings of 10- and 30-year securities, and $2 billion per quarter in both new issue and reopenings of 20-year securities. This path would reduce the supply of 20-year securities by a disproportionate amount to bring supply more in line with longer-term demand, and it would help to increase T-bill share close to the middle of TBAC’s recommended range of 15 to 20% over time. Auction sizes are expected to level out next quarter, though the group acknowledges Treasury may need to consider adjustments based on evolving fiscal needs. In the context of the financing recommendations, the Committee discussed the recent performance of the 20-year sector. While recent auctions have been

- range `[15, 20]` **← matches the configured band**

  > ld allow Treasury to meet its financing needs in an efficient manner while maintaining flexibility to accommodate further meaningful funding needs should they arise. Over a longer horizon, this issuance path is expected to keep the average maturity of Treasury debt and its average duration roughly unchanged; leave the T-bill share of outstanding debt within the recommended 15% to 20% range; and gradually increase the share of TIPS in outstanding debt. Of course, given the considerable uncertainty surrounding the economy and projected borrowing needs, Treasury will need to retain flexibility in its approach. Respectfully, _______________________________ Beth Hammack Chair, Treasury Borrowing Adviso

### 2nd Quarter

<https://home.treasury.gov/news/press-releases/jy0763>

- range `[15, 20]` **← matches the configured band**

  > s, $1 billion per quarter in both new issues and reopening of 10- and 30-year securities, and $3 billion in 20-year securities. This path would continue to reduce the supply of 7-year and 20-year securities by a disproportionate amount to bring supply more in line with longer-term demand, and it would help to maintain T-bill share within TBAC’s recommended range of 15 to 20 percent. Auction sizes are expected to level out next quarter, though the group acknowledges Treasury may need to consider further reductions based on evolving fiscal needs. Overall, the recommended path of auction sizes for the current and next quarter should allow Treasury to meet its financing needs in an efficient manner

- range `[15, 20]` **← matches the configured band**

  > fficient manner while maintaining flexibility to accommodate further meaningful funding needs should they arise. Over a longer horizon, this issuance path is expected to gradually lengthen the average maturity of Treasury debt and the average duration of debt to levels modestly above their historical ranges; leave the T-bill share of outstanding debt within the recommended 15% to 20% range; and gradually increase the share of TIPS in outstanding debt. Of course, given the considerable uncertainty surrounding the economy and projected borrowing needs, Treasury will need to retain flexibility in its approach and consider additional cuts if recent trends in receipts continue. Respectfully, __________

### 1st Quarter

<https://home.treasury.gov/news/press-releases/jy0580>

- range `[15, 20]` **← matches the configured band**

  > month in 7-year notes, $2 billion per quarter in both new issues and reopening of 10- and 30-year securities and $4 billion in 20-year securities). This path would continue to reduce the supply of 7-year and 20-year securities by a disproportionate amount to address the imbalance noted above and would help to maintain T-bill share within TBAC’s recommended range of 15-20%. Members expect that a smaller set of reductions would be desirable for the May quarter in total and that auction sizes would level out after that. The Committee debated whether cuts in May should be expected across the curve or primarily in longer maturities. Given that SOMA holdings can be viewed as floating-rate no

- range `[15, 20]` **← matches the configured band**

  > ncing needs in an efficient manner while maintaining flexibility to accommodate further meaningful funding needs should they arise. Over a longer horizon, this issuance path would lengthen the average maturity of Treasury debt and the average duration of debt to levels modestly above their historical ranges; leave the T-bill share of outstanding debt within the recommended 15% to 20% range; and gradually increase the share of TIPS in outstanding debt. Of course, given the considerable uncertainty surrounding current fiscal projections, the economy, and the Fed’s balance sheet policy, Treasury will need to retain flexibility in its approach. Respectfully, _______________________________ Beth Hammac

### 4th Quarter

<https://home.treasury.gov/news/press-releases/jy0463>

- range `[15, 20]` **← matches the configured band**

  > radual, perhaps somewhat slower than the baseline presented in the charge and Treasury should continue to monitor conditions to ensure demand remains robust. The second charge that the Committee reviewed explored the appropriate levels of T-bills as a share of outstanding debt. Without coupon cuts, it is expected that T-bills share would drop below the Committee’s recommended range of 15-20% of outstanding debt. There is considerable demand for short-term debt instruments in the current environment, as evidenced by the significant participation at the Fed’s reverse repo facility (RRP). In fact, this participation may be masking the richness that the T-bill sector would otherwise have reached, as the abili

- range `[15, 20]` **← matches the configured band**

  > onth) and $4 billion (for both new issues and reopenings in the quarter), respectively, which are somewhat larger than the declines in surrounding securities. It was expected that, based on current fiscal and economic projections, cuts to these issue sizes would need to continue for a few quarters in order to maintain T-bills in the recommended range of 15 to 20% of total debt outstanding over time. However, the Committee recognizes that a wide range of funding needs are possible, especially with fiscal legislation still pending, and that Treasury would need to adapt issuance plans based on incoming information over time. The group acknowledged that while these reductions are

- range `[15, 20]` **← matches the configured band**

  > ncing needs in an efficient manner while maintaining flexibility to accommodate further meaningful funding needs should they arise. Over a longer horizon, this issuance path would lengthen the average maturity of Treasury debt and the average duration of debt to levels modestly above their historical ranges; leave the T-bill share of outstanding debt within the recommended 15% to 20% range; and gradually increase the share of TIPS in outstanding debt. Of course, given the considerable uncertainty surrounding current fiscal projections, the economy, and the Fed’s balance sheet policy, Treasury will need to retain flexibility in its approach. Respectfully, _______________________________ Beth Hammac

### 3rd Quarter​

<https://home.treasury.gov/news/press-releases/jy0308>

- range `[15, 20]` **← matches the configured band**

  > harge that the Committee reviewed explored the appropriate adjustments to Treasury issuance in upcoming quarters in light of current fiscal forecasts. The presenting member relied on a participant model to review several scenarios with the goals of maintaining a regular and predictable issuance pattern and keeping the T-bill share of total outstanding debt between TBAC’s recommended range of 15% and 20%. The member noted that, under a variety of assumptions, maintaining the current coupon auction sizes would result in a T-bill share that would fall to near zero by 2026, highlighting the degree of overfunding under current auction sizes. The member ran two more plausible scenarios as a baseline for the discussion. In

- range `[15, 20]` **← matches the configured band**

  > 0-year securities, the Committee recommends declines of $3 billion and $4 billion, respectively2, which are somewhat larger than the declines in surrounding securities. It was expected that, based on current fiscal and economic projections, these cuts would need to be sustained over a few quarters in order to maintain T-bills in the recommended range of 15 to 20% of total debt outstanding over time. However, the Committee recognizes that a wide range of funding needs are possible and that Treasury would need to adapt issuance plans based on incoming information over time. The group acknowledged that while these reductions are sizeable, the gradual pace of the adjustment and th

- range `[15, 20]` **← matches the configured band**

  > to meet its financing needs in an efficient manner while maintaining flexibility to accommodate further meaningful funding needs should they arise. Over a longer horizon, this issuance path would lengthen the average maturity of Treasury debt and the average duration of debt to above their historical ranges; leave the T-bill share of outstanding debt on a general downward trajectory, leveling out within the recommended 15% to 20% range; and gradually increase the share of TIPS in outstanding debt. Of course, given the considerable uncertainty surrounding current fiscal projections, the economy, and the Fed’s balance sheet policy, Treasury will need to retain flexibility in its approach. Finally, the Committee reviewed a charge reviewing money

### 2nd Quarter

<https://home.treasury.gov/news/press-releases/jy0165>

- range `[15, 20]` **← matches the configured band**

  > mittee noted that prior increases in coupon issuance will continue to result in sizable net funding to Treasury going forward. Maintaining current auction sizes for nominal coupon securities would result in a higher level of net funding than needed in coming years, requiring Treasury to reduce the outstanding stock of Treasury bills to levels below the TBAC’s prior recommended range of 15-20% of outstanding debt. Thus, the Committee anticipates that Treasury may want to reduce nominal coupon sizes beginning late this year or early next year. Additionally, Committee members recognize that a wide range of funding needs are possible and that information about both fiscal and economic outcomes in coming quarte

- range `[15, 20]` **← matches the configured band**

  > intaining flexibility to accommodate further meaningful funding needs should they arise. Over a longer horizon, we recommend an issuance path that would lengthen the average maturity of Treasury debt to above its historical range; gradually reduce the share of debt maturing within one, three, and five years; leave the T-bill share of outstanding debt on a general downward trajectory, leveling out within the recommended 15% to 20% range; and gradually increase the share of TIPS in outstanding debt. Of course, given the considerable uncertainty surrounding current fiscal projections, the economy, and the Fed’s balance sheet policy, Treasury will need to retain flexibility in its approach. Finally, the Committee reviewed a charge on recent Treasu

### 1st Quarter

<https://home.treasury.gov/news/press-releases/jy0018>

- range `[15, 20]` **← matches the configured band**

  > ed path of auction sizes should allow Treasury to continue reducing funding risk, while maintaining flexibility to accommodate further meaningful funding needs should they arise. The path would be expected to lengthen the average maturity of Treasury debt back to its pre-COVID levels over time. It would also leave the T-bill share of outstanding debt on a general downward trajectory over the next couple of years, toward the 15% to 20% range that TBAC had previously recommended. Of course, given the considerable uncertainty surrounding current fiscal projections, the economy, and the Fed’s balance sheet policy, Treasury will need to retain flexibility in its approach. Finally, Committee members continue to encourage Treasury to announce a SOFR FRN.

### 4th Quarter​​

<https://home.treasury.gov/news/press-releases/sm1175>

- range `[15, 20]` **← matches the configured band**

  > ble to protect against rising rates and to minimize operational risk with frequent issuance. Moreover, reducing the share of T-bills would better enable them to continue serving as an effective shock absorber for unexpected financing needs. Based on these considerations, the Committee recommended allowing the share of T-Bills to decline gradually to a range of 15% to 20% of outstanding debt. The Committee next discussed financing strategies to accommodate revised fiscal projections amidst continued fiscal and economic uncertainty owing to the COVID-19 epidemic and today’s election. Prior increases in coupon issuance will continue to result in sizable net funding to Treasury for severa

### 2nd Quarter

<https://home.treasury.gov/news/press-releases/sm678>

- range `[25, 33]`

  > nt fiscal projections, and in line with the February recommendations, the Committee suggested no change to coupon issue sizes for this quarter, and expected little or no change to nominal issuance for the remainder of FY 2019. The Committee acknowledged that maintaining current issue sizes would require a reduction in bills issuance over the near term, and reduce the proportion of bills below TBAC‘s prior recommendation of 25-33% of new issuance. The Committee noted that the 25-33% of issuance target was a longer-term average goal and that Treasury should respond to transient changes in borrowing needs, as it has historically, by changing bill auctions sizes as necessary. The Committee agreed that maintaining current coupon sizes was most cons

- range `[25, 33]`

  > tle or no change to nominal issuance for the remainder of FY 2019. The Committee acknowledged that maintaining current issue sizes would require a reduction in bills issuance over the near term, and reduce the proportion of bills below TBAC‘s prior recommendation of 25-33% of new issuance. The Committee noted that the 25-33% of issuance target was a longer-term average goal and that Treasury should respond to transient changes in borrowing needs, as it has historically, by changing bill auctions sizes as necessary. The Committee agreed that maintaining current coupon sizes was most consistent with Treasury’s regular and predictable issuance strategy to provide lowest cost to the taxpayers over time, particularly as 2020 and especially 2021 could require further coupon increases given current fiscal p

### 4th Quarter

<https://home.treasury.gov/news/press-releases/sm0201>

- range `[25, 33]`

  > cating around one-third of the financing gap to T-bills would make sense. Anything much above that share could shorten the weighted average maturity (WAM) and necessitate T-bill auction sizes that approach the primary dealer maximum estimates. There was general agreement among the Committee members that increasing the T-bill share of issuance to somewhere between 25% and 33% (over what’s required for the cash balance detailed in the Treasury’s liquidity management framework) made sense given the supply and demand dynamics described in the presentation. The second TBAC charge was to provide an update and extension on the efforts the Committee has made on developing optimal issuance models.

