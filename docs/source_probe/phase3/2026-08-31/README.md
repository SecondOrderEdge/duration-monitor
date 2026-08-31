# Phase 3 source discovery

- Probe run (UTC): `2026-08-31T13:57:35.536388+00:00`

What each candidate publisher actually returns. This is DISCOVERY — no field names are declared yet, so nothing here is verified. It exists so the Phase 3 schema is designed against observed responses rather than assumptions, which is what the Phase 1 probe was for.

| source | publisher | reachable | would feed |
|---|---|---|---|
| `bis` | Bank for International Settlements | yes | bill share, maturity composition |
| `ecb` | European Central Bank | yes | bill share, net issuance, term premium inputs |
| `eurostat` | Eurostat | yes | bill share, debt composition |
| `france_aft` | Agence France Trésor | yes | bill share, WAM |
| `germany_finanzagentur` | Deutsche Finanzagentur | yes | bill share, auction stress |
| `italy_mef` | Italian Treasury (MEF) | yes | bill share, WAM |
| `japan_mof` | Japan Ministry of Finance | yes | bill share, WAM |
| `oecd` | OECD | yes | WAM proxy, maturity buckets |
| `uk_dmo` | UK Debt Management Office | yes | bill share, WAM, auction stress |

## ECB coverage depth

How far back each candidate series reaches. The point-in-time percentiles need 60 months before the score publishes at all, so this decides feasibility before any design question does.

| series | first | last | key |
|---|---|---|---|
40,633 series in the dataflow; 36 match central government, monthly, short or long-term, stocks or net issues.

| `FR_F33100_1` | 2012-12 | 2022-03 | `M.FR.S131.F33100.N.1.Z06.E.Z` |
| `FR_F33100_4` | 2012-12 | 2022-03 | `M.FR.S131.F33100.N.4.Z06.E.Z` |
| `FR_F33200_1` | 2012-12 | 2022-03 | `M.FR.S131.F33200.N.1.Z06.E.Z` |
| `FR_F33200_4` | 2012-12 | 2022-03 | `M.FR.S131.F33200.N.4.Z06.E.Z` |

## Eurostat coverage depth

| geo | periods | first | last |
|---|---|---|---|
| DE | 129 | 1994-Q1 | 2026-Q1 |
| FR | 129 | 1994-Q1 | 2026-Q1 |
| IT | 129 | 1994-Q1 | 2026-Q1 |

## `bis` — Bank for International Settlements

Debt securities statistics by residence, sector and maturity. The brief names it first for cross-sovereign comparability.

### `https://stats.bis.org/api/v1/dataflow/BIS`

- HTTP 200, `application/xml;charset=UTF-8`, 15,287 bytes

```
<?xml version="1.0" ?><mes:Structure xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:mes="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:str="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:com="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"><mes:Header><mes:ID>IDREF310b7fab-12cd-48b0-957a-e3c7fa558262</mes:ID><mes:Test>false</mes:Test><mes:Prepared>2026-08-30T15:16:19Z</mes:Prepared><mes:Sender id="UNKNOWN"></mes:Sender><mes:Receiver id="not_supplied"></mes:Receiver></mes:Header><mes:Structures><str:Dataflows><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=BIS:BIS_REL_CAL(1.0)" isExternalReference="false" agencyID="BIS" id="BIS_REL_CAL" isFinal="false" version="1.0"><com:Name xml:lang="en">BIS_RELEASE_CALENDAR</com:Name><str:Structure><Ref package="datastructure" agencyID="BIS" id="BIS_RELEASE_CALENDAR" version="1.0" class="DataStructure"></Ref></str:Structure></str:Dataflow><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=BIS:WS_CBPOL(1.0)" isExternalReference="false" agencyID="BIS" id="WS_CBPOL" isFinal="false" version="1.0"><com:Name xml:lang="en">Central bank policy rates</co
```

### `https://stats.bis.org/api/v1/dataflow`

- HTTP 200, `application/xml;charset=UTF-8`, 16,687 bytes

```
<?xml version="1.0" ?><mes:Structure xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:mes="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:str="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:com="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"><mes:Header><mes:ID>IDREFb94ce49a-fe52-44be-b055-30e80a1f9fba</mes:ID><mes:Test>false</mes:Test><mes:Prepared>2026-08-31T05:17:47Z</mes:Prepared><mes:Sender id="UNKNOWN"></mes:Sender><mes:Receiver id="not_supplied"></mes:Receiver></mes:Header><mes:Structures><str:Dataflows><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=BIS:BIS_REL_CAL(1.0)" isExternalReference="false" agencyID="BIS" id="BIS_REL_CAL" isFinal="false" version="1.0"><com:Name xml:lang="en">BIS_RELEASE_CALENDAR</com:Name><str:Structure><Ref package="datastructure" agencyID="BIS" id="BIS_RELEASE_CALENDAR" version="1.0" class="DataStructure"></Ref></str:Structure></str:Dataflow><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=BIS:WS_CBPOL(1.0)" isExternalReference="false" agencyID="BIS" id="WS_CBPOL" isFinal="false" version="1.0"><com:Name xml:lang="en">Central bank policy rates</co
```

### `https://www.bis.org/statistics/index.htm`

- **http_error**: `404`

## `ecb` — European Central Bank

Securities issues statistics and government finance statistics cover Germany, France and Italy on one basis, which is three of the five Phase 3 sovereigns from a single publisher.

### `https://data-api.ecb.europa.eu/service/data/SEC/Q.I9.1000.F33000.N.I.Z01.A?lastNObservations=1&format=jsondata`

- **http_error**: `400`

### `https://data-api.ecb.europa.eu/service/data/SEC?lastNObservations=1&format=jsondata&detail=serieskeysonly`

- HTTP 200, `application/vnd.sdmx.data+json;version=1.0.0-wd`, 994,250 bytes
- JSON top-level keys: `['dataSets', 'header', 'structure']`
- **series:FREQ** (Frequency) — 2 categories: `M`=Monthly, `A`=Annual
- **series:REF_AREA** (Reference area) — 33 categories: `AT`=Austria, `I8`=Euro area 19 (fixed composition) as of 1 January 2015, `A1`=World (all entities), `HU`=Hungary, `HR`=Croatia, `SE`=Sweden, `V3`=EU 28 (fixed composition) as of 1 July 2013, `V5`=EU27 (fixed composition) as of 31 January 2020 (brexit)
- **series:SEC_ISSUING_SECTOR** (Securities issuing sector) — 22 categories: `1100`=Non-financial corporations (ESA 95 classification), `1210`=The central bank, `1220`=Other monetary financial institutions, `1230`=Other financial intermediaries, except insurance corporations and pension funds (ESA 95 classification), `1314`=Social security funds, `1610`=Non-MFI corporations, `2000`=Rest of the world, `1000`=Total economy
- **series:SEC_ITEM** (Securities item) — 6 categories: `F33200`=Long-term securities other than shares, `F33201`=Long-term / Fixed rate issues, `F33202`=Long-term / Floating rate issues, `F51100`=Listed shares, `F33000`=Securities other than shares, excluding financial derivatives, `F33100`=Short-term securities other than shares
- **series:SEC_VALUATION** (Securities valuation) — 2 categories: `N`=Nominal value, `M`=ESA95 valuation
- **series:DATA_TYPE_SEC** (Securities data type) — 7 categories: `3`=Redemptions (flows), `4`=Net issues (flows), `1`=Outstanding amounts at the end of the period (stocks), `2`=(Gross) issues against cash (flows), `A`=Based on 13-month average, `I`=Index of Notional Stocks, `Q`=Based on 4-month average
- **series:CURRENCY_TRANS** (Currency of transaction) — 13 categories: `Z06`=All currencies except EUR, `EUR`=Euro, `Z01`=All currencies combined, `HUF`=Hungarian forint, `Z07`=All currencies other than domestic, Euro and euro area currencies, `HRK`=Croatian kuna, `SEK`=Swedish krona, `RON`=Romanian leu
- **series:SERIES_DENOM** (Series denominat/spec calcul) — 5 categories: `E`=Euro, `A`=Annual growth rate, `3`=3 month annualised growth rate, `6`=6 month annualised growth rate, `N`=National currency
- **series:SEC_SUFFIX** (Series suffix - SEC context) — 3 categories: `Z`=Unspecified, `S`=Seasonally adjusted, `P`=Percentage of total currencies

```
{"header":{"id":"2004c8fa-a166-4821-95e2-a5f5b3e62d3b","test":false,"prepared":"2026-08-31T15:57:44.384+02:00","sender":{"id":"ECB"}},"dataSets":[{"action":"Replace","validFrom":"2026-08-31T15:57:44.384+02:00","series":{"0:0:0:0:0:0:0:0:0":{},"0:0:0:0:0:1:1:0:0":{},"0:0:0:0:0:1:2:0:0":{},"0:0:0:0:0:1:0:0:0":{},"0:0:0:1:0:2:1:0:0":{},"0:0:0:1:0:2:2:0:0":{},"0:0:0:1:0:2:0:0:0":{},"0:0:0:1:0:3:1:0:0":{},"0:0:0:1:0:3:2:0:0":{},"0:0:0:1:0:3:0:0:0":{},"0:0:0:1:0:0:1:0:0":{},"0:0:0:1:0:0:2:0:0":{},"0:0:0:1:0:0:0:0:0":{},"0:0:0:1:0:1:1:0:0":{},"0:0:0:1:0:1:2:0:0":{},"0:0:0:1:0:1:0:0:0":{},"0:0:0:2:0:2:1:0:0":{},"0:0:0:2:0:2:2:0:0":{},"0:0:0:2:0:2:0:0:0":{},"0:0:0:2:0:3:1:0:0":{},"0:0:0:2:0:3:2:0:0":{},"0:0:0:2:0:3:0:0:0":{},"0:0:0:2:0:0:1:0:0":{},"0:0:0:2:0:0:2:0:0":{},"0:0:0:2:0:0:0:0:0":{},"0:0:0:2:0:1:1:0:0":{},"0:0:0:2:0:1:2:0:0":{},"0:0:0:2:0:1:0:0:0":{},"0:0:0:3:1:2:1:0:0":{},"0:0:0:3:1:2:2:0:0":{},"0:0:0:3:1:2:0:0:0":{},"0:0:0:3:1:3:1:0:0":{},"0:0:0:3:1:3:2:0:0":{},"0:0:0:3:1:3:0:0:0":{},"0:0:0:3:1:0:1:0:0":{},"0:0:0:3:1:0:2:0:0":{},"0:0:0:3:1:0:0:0:0":{},"0:0:0:3:1:1:1:0:0":{},"0:0:0:3:1:1:2:0:0":{},"0:0:0:3:1:1:0:0:0":{},"0:0:1:4:0:2:1:0:0":{},"0:0:1:4:0:3:1:0:0":{},"0:0:1:4:0:0:1
```

### `https://data-api.ecb.europa.eu/service/datastructure/ECB/ECB_SEC1?format=sdmx-json`

- HTTP 200, `application/vnd.sdmx.structure+xml;version=2.1`, 30,851 bytes

```
<?xml version='1.0' encoding='UTF-8'?><mes:Structure xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xml="http://www.w3.org/XML/1998/namespace" xmlns:mes="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:str="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:com="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"><mes:Header><mes:ID>IREF846627</mes:ID><mes:Test>false</mes:Test><mes:Prepared>2026-08-31T13:57:46Z</mes:Prepared><mes:Sender id="Unknown"/><mes:Receiver id="not_supplied"/></mes:Header><mes:Structures><str:DataStructures><str:DataStructure urn="urn:sdmx:org.sdmx.infomodel.datastructure.DataStructure=ECB:ECB_SEC1(1.0)" isExternalReference="false" agencyID="ECB" id="ECB_SEC1" isFinal="false" uri="https://www.ecb.europa.eu/vocabulary/stats/sec/1" version="1.0"><com:Name xml:lang="en">Securities</com:Name><str:DataStructureComponents><str:DimensionList urn="urn:sdmx:org.sdmx.infomodel.datastructure.DimensionDescriptor=ECB:ECB_SEC1(1.0).DimensionDescriptor" id="DimensionDescriptor"><str:Dimension urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dimension=ECB:ECB_SEC1(1.0).FREQ" id="FREQ" position="1"><str:ConceptIdentity><Ref m
```

## `eurostat` — Eurostat

Government debt by instrument and maturity (gov_10q_ggdebt), quarterly, harmonised across member states.

### `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10q_ggdebt?format=JSON&lang=EN&geo=DE&time=2025-Q4`

- HTTP 200, `application/json`, 8,880 bytes
- JSON top-level keys: `['class', 'dimension', 'extension', 'id', 'label', 'size', 'source', 'status', 'updated', 'value', 'version']`
- **freq** (Time frequency) — 1 categories: `Q`=Quarterly
- **na_item** (National accounts indicator (ESA 2010)) — 20 categories: `F2`=Currency and deposits, `F21`=Currency, `F22_F29`=Transferable deposits; other deposits, `F3`=Debt securities, `F31`=Short-term debt securities, `F32`=Long-term debt securities, `F4`=Loans, `F41`=Short-term - loans
- **sector** (Sector) — 8 categories: `S11001`=Public non-financial corporations, `S13`=General government, `S1311`=Central government, `S13111`=Budgetary central government, `S13112`=Central government other than budgetary central government, `S1312`=State government, `S1313`=Local government, `S1314`=Social security funds
- **unit** (Unit of measure) — 4 categories: `MIO_EUR`=Million euro, `MIO_NAC`=Million units of national currency, `PC_GDP`=Percentage of gross domestic product (GDP), `PC_TOT`=Percentage of total
- **geo** (Geopolitical entity (reporting)) — 1 categories: `DE`=Germany
- **time** (Time) — 1 categories: `2025-Q4`=2025-Q4

```
{"version":"2.0","class":"dataset","label":"Quarterly government debt","source":"ESTAT","updated":"2026-07-21T11:00:00+0200","value":{"4":18278.2,"5":18278.2,"6":0.4,"7":0.6,"8":18278.2,"9":18278.2,"10":0.4,"11":0.6,"20":0.0,"21":0.0,"22":0.0,"23":0.0,"24":0.0,"25":0.0,"26":0.0,"27":0.0,"28":0.0,"29":0.0,"30":0.0,"31":0.0,"36":0.0,"37":0.0,"38":0.0,"39":0.0,"40":0.0,"41":0.0,"42":0.0,"43":0.0,"52":0.0,"53":0.0,"54":0.0,"55":0.0,"56":0.0,"57":0.0,"58":0.0,"59":0.0,"60":0.0,"61":0.0,"62":0.0,"63":0.0,"68":18278.2,"69":18278.2,"70":0.4,"71":0.6,"72":18278.2,"73":18278.2,"74":0.4,"75":0.6,"84":0.0,"85":0.0,"86":0.0,"87":0.0,"88":0.0,"89":0.0,"90":0.0,"91":0.0,"92":0.0,"93":0.0,"94":0.0,"95":0.0,"100":2239852.4,"101":2239852.4,"102":50.1,"103":78.9,"104":1789103.4,"105":1789103.4,"106":40.0,"107":63.0,"116":459977.8,"117":459977.8,"118":10.3,"119":16.2,"120":2618.1,"121":2618.1,"122":0.1,"123":0.1,"124":0.0,"125":0.0,"126":0.0,"127":0.0,"132":99394.7,"133":99394.7,"134":2.2,"135":3.5,"136":94948.2,"137":94948.2,"138":2.1,"139":3.3,"148":4649.0,"149":4649.0,"150":0.1,"151":0.2,"152":0.0,"153":0.0,"154":0.0,"155":0.0,"156":0.0,"157":0.0,"158":0.0,"159":0.0,"164":2140457.7,"165":2140457.7,
```

### `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10q_ggdebt?format=JSON&lang=EN&geo=IT&time=2025-Q4`

- HTTP 200, `application/json`, 7,962 bytes
- JSON top-level keys: `['class', 'dimension', 'extension', 'id', 'label', 'size', 'source', 'status', 'updated', 'value', 'version']`
- **freq** (Time frequency) — 1 categories: `Q`=Quarterly
- **na_item** (National accounts indicator (ESA 2010)) — 20 categories: `F2`=Currency and deposits, `F21`=Currency, `F22_F29`=Transferable deposits; other deposits, `F3`=Debt securities, `F31`=Short-term debt securities, `F32`=Long-term debt securities, `F4`=Loans, `F41`=Short-term - loans
- **sector** (Sector) — 8 categories: `S11001`=Public non-financial corporations, `S13`=General government, `S1311`=Central government, `S13111`=Budgetary central government, `S13112`=Central government other than budgetary central government, `S1312`=State government, `S1313`=Local government, `S1314`=Social security funds
- **unit** (Unit of measure) — 4 categories: `MIO_EUR`=Million euro, `MIO_NAC`=Million units of national currency, `PC_GDP`=Percentage of gross domestic product (GDP), `PC_TOT`=Percentage of total
- **geo** (Geopolitical entity (reporting)) — 1 categories: `IT`=Italy
- **time** (Time) — 1 categories: `2025-Q4`=2025-Q4

```
{"version":"2.0","class":"dataset","label":"Quarterly government debt","source":"ESTAT","updated":"2026-07-21T11:00:00+0200","value":{"4":170659.6,"5":170659.6,"6":7.6,"7":5.5,"8":170659.6,"9":170659.6,"10":7.6,"11":5.5,"68":170659.6,"69":170659.6,"70":7.6,"71":5.5,"72":170659.6,"73":170659.6,"74":7.6,"75":5.5,"100":2605807.7,"101":2605807.7,"102":115.4,"103":84.2,"104":2620964.9,"105":2620964.9,"106":116.1,"107":84.7,"120":7414.8,"121":7414.8,"122":0.3,"123":0.2,"132":130157.4,"133":130157.4,"134":5.8,"135":4.2,"136":130357.6,"137":130357.6,"138":5.8,"139":4.2,"152":0.0,"153":0.0,"154":0.0,"155":0.0,"164":2475650.3,"165":2475650.3,"166":109.6,"167":80.0,"168":2490607.3,"169":2490607.3,"170":110.3,"171":80.4,"184":7414.8,"185":7414.8,"186":0.3,"187":0.2,"196":319420.3,"197":319420.3,"198":14.1,"199":10.3,"200":247176.8,"201":247176.8,"202":10.9,"203":8.0,"216":98409.5,"217":98409.5,"218":4.4,"219":3.2,"220":75.2,"221":75.2,"222":0.0,"223":0.0,"228":35919.2,"229":35919.2,"230":1.6,"231":1.2,"232":32158.9,"233":32158.9,"234":1.4,"235":1.0,"248":3694.9,"249":3694.9,"250":0.2,"251":0.1,"252":65.4,"253":65.4,"254":0.0,"255":0.0,"260":283501.1,"261":283501.1,"262":12.6,"263":9.2,"264":21
```

## `france_aft` — Agence France Trésor

OAT and BTF issuance and outstanding.

### `https://www.aft.gouv.fr/en`

- HTTP 200, `text/html; charset=UTF-8`, 77,727 bytes

```
<!DOCTYPE html>
<html lang="en" dir="ltr">
  <head>
    <meta charset="utf-8" />
<link rel="shortlink" href="https://www.aft.gouv.fr/en" />
<link rel="canonical" href="https://www.aft.gouv.fr/en" />
<meta name="MobileOptimized" content="width" />
<meta name="HandheldFriendly" content="true" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<script><!-- Tag standard + extension opt-out complet - Eulerian Analytics  -->
  (function(e,a){var i=e.length,y=5381,k='script',z='_EA_',zd=z+'disabled',s=window,v=document,
    o=v.createElement(k),l=s.localStorage;for(;i;){i-=1;y=(y*33)^e.charCodeAt(i)}y=z+(y>>>=0);
    (function(e,a,s,y,z,zd,l){s[a]=s[a]||function(){(s[y]=s[y]||[]).push(arguments);s[y].eah=e;};
    s[zd]=function(){return l.getItem(z);};s[z+'toggle']=function(){(s[zd]())?l.removeItem(z):l.setItem(z,1);}}(e,a,s,y,z,zd,l));
    if(!s[zd]()){i=new Date/1E7|0;o.ea=y;y=i%26;o.async=1;o.src='//'+e+'/'+String.fromCharCode(97+y,122-y,65+y)+(i%1E3)+'.js?2';
    s=v.getElementsByTagName(k)[0];s.parentNode.insertBefore(o,s);}})('gva.et-gv.fr','EA_push');
</script>
<link rel="icon" href="/favicon.ico" type="image/vnd.microsoft.icon" />

    <title>Agence France
```

## `germany_finanzagentur` — Deutsche Finanzagentur

Bund issuance calendar and outstanding securities.

### `https://www.deutsche-finanzagentur.de/en/`

- HTTP 200, `text/html; charset=utf-8`, 226,580 bytes

```
<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="utf-8">

<!-- 
	created by BippesBrandão GmbH (https://www.bippesbrandao.de  - kontakt@bippesbrandao.de)
	    ===

	This website is powered by TYPO3 - inspiring people to share!
	TYPO3 is a free open source Content Management Framework initially created by Kasper Skaarhoj and licensed under GNU/GPL.
	TYPO3 is copyright 1998-2026 of Kasper Skaarhoj. Extensions are copyright of their respective owners.
	Information and contribution at https://typo3.org/
-->


<title>Home - Deutsche Finanzagentur</title>
<meta http-equiv="x-ua-compatible" content="IE=edge">
<meta name="generator" content="TYPO3 CMS">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index, follow">
<meta name="description" content="Bundesrepublik Deutschland Finanzagentur GmbH">
<meta name="keywords" content="Finanzagentur, Institutionelle Investoren, Private Anleger">
<meta name="author" content="Deutsche Finanzagentur">
<meta property="og:locale" content="de_DE">
<meta property="og:locale:alternate" content="en_GB">
<meta property="og:title" content="Home - Deutsche Finanzagentur">
<meta property="og:site_na
```

## `italy_mef` — Italian Treasury (MEF)

BOT and BTP issuance and outstanding.

### `https://www.dt.mef.gov.it/en/debito_pubblico/`

- HTTP 200, `text/html;charset=UTF-8`, 674,215 bytes

```
<!DOCTYPE html>
<html lang="it">
	<head>
		
















	
	
	


<meta charset="utf-8" />
<meta http-equiv="X-UA-Compatible" content="IE=edge" />
<!-- TITLE DI PAGINA -->
 

	
		<title>Public Debt - MEF Department of Treasury </title> 
		<meta name="title" content="Public Debt - MEF Department of Treasury" />	     
	    
	


<meta name="description" content="" />
<meta name="keywords" content="" />
<meta name="viewport" content="width=device-width, initial-scale=1, minimum-scale=1, maximum-scale=2" />
<meta name="robots" content="index,follow" />
<meta name="revisit-after" content="7 DAYS" />
<meta name="language" content="en" />
<meta name="rating" content="General" />

<!-- ICON -->
<link rel="icon" type="image/x-icon" href="/system/modules/it.acn.dipartimentotesoro/resources/img/favicon.ico"/>

<!-- STYLES -->
<link rel="stylesheet" href="/export/system/modules/it.acn.dipartimentotesoro/resources/assets/vendor/swiper/css/swiper.min.css" />
<link rel="stylesheet" href="/export/system/modules/it.acn.dipartimentotesoro/resources/assets/vendor/bootstrap/css/bootstrap.css" />
<link rel="stylesheet" href="/export/system/modules/it.acn.dipartimentotesoro/resources/assets/css/style.c
```

## `japan_mof` — Japan Ministry of Finance

JGB issuance and outstanding by maturity. Japan is the largest test of the thesis outside the US.

### `https://www.mof.go.jp/english/policy/jgbs/index.html`

- HTTP 200, `text/html`, 21,912 bytes

```
<!DOCTYPE html>
<html lang="en">


<head prefix="og: http://ogp.me/ns# fb: http://ogp.me/ns/fb# article: http://ogp.me/ns/article#">
  <!-- meta -->
  <meta charset="UTF-8">
  <meta name="robots" content="index,follow">
  <meta http-equiv="X-UA-Compatible" content="IE=Edge" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="format-detection" content="telephone=no">
  <meta name="copyright" content="Copyright (C) Ministry of Finance, The Japanese Government" />
  <meta name="description" content="Japanese Government Bonds" />
  <meta name="keywords" content="Japanese Government Bonds" />
  <meta name="date" content="2026-05-29" />

  <!-- og -->
  <meta property="og:title" content="Japanese Government Bonds : Ministry of Finance" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="https://www.mof.go.jp/english/policy/jgbs/index.html" />
  <meta property="og:image" content="https://www.mof.go.jp/english/common/images/og_img.png" />
  <meta property="og:site_name" content="Ministry of Finance" />
  <meta property="fb:app_id" content="253099528071523" />
  <title>Japanese Government Bonds : Ministry of Finance</ti
```

### `https://www.mof.go.jp`

- HTTP 200, `text/html`, 46,661 bytes
- redirected to `https://www.mof.go.jp/`

```
﻿<!DOCTYPE html>
<html lang="ja">

<head prefix="og: http://ogp.me/ns# fb: http://ogp.me/ns/fb# website: http://ogp.me/ns/website#">
  <!-- meta -->
  <meta charset="UTF-8">
  <meta name="robots" content="index,follow">
  <meta http-equiv="X-UA-Compatible" content="IE=Edge" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="format-detection" content="telephone=no">
  <meta name="copyright" content="Copyright (C) 財務省 Ministry of Finance, The Japanese Government" />
  <meta name="description" content="財務省トップページ" />
  <meta name="keywords" content="財務省,MOF,Ministry of Finance Japan,トップページ,予算,決算,財政,税制,国債,関税,国庫,通貨,国有財産,財政投融資,政策金融,たばこ,塩" />
  <meta name="date" content="2026-08-19" />

  <!-- og -->
  <meta property="og:title" content="財務省ホームページ" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://www.mof.go.jp/index.htm" />
  <meta property="og:image" content="https://www.mof.go.jp/common/images/og_img.png" />
  <meta property="og:site_name" content="財務省" />
  <meta property="fb:app_id" content="253099528071523" />
  <title>財務省</title>

  <!-- icon -->
  <link rel="shortcut icon" href="/favicon.ico">
  <link
```

## `oecd` — OECD

Central government debt statistics, including maturity structure on a harmonised basis across members.

### `https://sdmx.oecd.org/public/rest/dataflow/OECD.GOV.GSD?format=sdmx-json`

- **http_error**: `404`

### `https://sdmx.oecd.org/public/rest/dataflow`

- HTTP 200, `application/vnd.sdmx.structure+xml; version=2.1; charset=utf-8`, 8,894,080 bytes

```
<?xml version="1.0" encoding="utf-8"?>
<!--NSI Web Service v8.19.8.0-->
<message:Structure xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:structure="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:common="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common">
  <message:Header>
    <message:ID>IDREF10609</message:ID>
    <message:Test>false</message:Test>
    <message:Prepared>2026-08-31T15:58:03.6505619+02:00</message:Prepared>
    <message:Sender id="Unknown" />
    <message:Receiver id="Unknown" />
  </message:Header>
  <message:Structures>
    <structure:Dataflows>
      <structure:Dataflow id="SEEA_AEA_A" agencyID="ESTAT" version="1.4" isFinal="true">
        <common:Annotations>
          <common:Annotation>
            <common:AnnotationType>NonProductionDataflow</common:AnnotationType>
            <common:AnnotationText xml:lang="en">true</common:AnnotationText>
          </common:Annotation>
        </common:Annotations>
        <common:Name xml:lang="en">Air Emissions Accounts</common:Name>
        <common:Description xml:lang="en">Air Emissions Accounts</common:Description>
        <structure:St
```

## `uk_dmo` — UK Debt Management Office

Gilt and Treasury bill issuance, per-security detail. The UK is the closest analogue to the US data estate.

### `https://www.dmo.gov.uk`

- HTTP 200, `text/html; charset=utf-8`, 33,314 bytes
- redirected to `https://www.dmo.gov.uk/`

```


<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Home</title>
    <meta name="viewport" content="width=device-width" />
        <meta name="description" content="DMO" />
        <meta name="keywords" content="debt, management, office, treasury, bonds, gilts" />
        <meta name="author" content="Debt Management Office" />
        <meta property="og:title" content="" />
        <meta property="og:description" content="DMO" />
        <meta property="og:image" content="" />
        <meta property="og:url" content="/" />
        <meta property="og:type" content="" />
        <meta property="og:locale" content="en" />
    <link rel="apple-touch-icon-precomposed" sizes="57x57" href="/dist/favicons/dmo/apple-touch-icon-57x57.png" />
<link rel="apple-touch-icon-precomposed" sizes="114x114" href="/dist/favicons/dmo/apple-touch-icon-114x114.png" />
<link rel="apple-touch-icon-precomposed" sizes="72x72" href="/dist/favicons/dmo/apple-touch-icon-72x72.png" />
<link rel="apple-touch-icon-precomposed" sizes="144x144" href="/dist/favicons/dmo/apple-touch-icon-144x144.png" />
<link rel="apple-touch-icon-precomposed" sizes="60x60" href="/dist/f
```

### `https://www.dmo.gov.uk/data/`

- HTTP 200, `text/html; charset=UTF-8`, 15,242 bytes
- redirected to `https://validate.perfdrive.com/5e975472fcf167bd1130d74f0fb9a2f7/?ssa=de9d5ab0-2670-4e98-97e5-af3c79e221a0&ssb=48067291234&ssc=https%3A%2F%2Fwww.dmo.gov.uk%2Fdata%2F&ssi=f2202341-bhbz-4a70-8d64-d339f7d6ba4e&ssk=support@shieldsquare.com&ssm=50356739561455370106844317584663&ssn=9556645b9c6440a004286b14e99fa0e7602f2028ab81-cc7a-4d4c-a666f0&sso=29e7edc6-eeee83efda84299353a24b7f175a2cfd33c3d4b14294690d&ssp=93286666411788168036178810038911861&ssq=20407218469734045161284697940811955679859&ssr=MTcyLjE4NC4yMDkuMTg2&sst=python-requests/2.33.1&ssu=&ssv=&ssw=&ssx=eyJfX3V6bWYiOiI3ZjkwMDAyMDI4YWI4MS1jYzdhLTRkNGMtYWRjNi1lZWVlODNlZmRhODQxLTE3ODgxODQ2OTcwNzAwLTAwNDhlYzNhZDAzNzRjMGVlYTUxMCIsInV6bXgiOiI3ZmMwMDBmOTkwMmUzYi00YThiLTRkYmEtYTIxZS1kMDAyODE0ODAxZWIxLTE3ODgxODQ2OTcwNzAwLTAwM2E5YzczMDY1MzhiMjVhYWUxMCIsInJkIjoiZG1vLmdvdi51ayJ9`

```
<head><title>ShieldSquare Captcha</title><script type="text/javascript">
	window.SSJSInternal = 18155;

	var __uzdbm_1 = "2028ab81-cc7a-4d4c-adc6-eeee83efda84";
	var __uzdbm_2 = "ZjIyMDIzNDEtYmhiei00YTcwLThkNjQtZDMzOWY3ZDZiYTRlJDE3Mi4xODQuMjA5LjE4Ng==";
	
	(function(w, d, e, u, c, g, a, b){
		w["SSJSConnectorObj"] = w["SSJSConnectorObj"] || {ss_cid : c, domain_info: g};
		a = d.createElement(e);
		a.async = true;
		a.src = u;
		b = d.getElementsByTagName(e)[0];
		b.parentNode.insertBefore(a, b);
	})(window,document,"script","https://cdn.perfdrive.com/aperture/aperture.js","b8c3","auto");
</script>

<script type="text/javascript">
function _0x147a(){var _0x2ec979=['ecb5e100e5a9a3e7f6d1fd97512215282','mousemove','toGMTString','0xcvd','1976572igpWBa','touches','1993290amMtaY','block','2128497rXvxFu','Udr9HvhYUw','getTime','style','parentElement','5876928iktpYv',';\x20path=/','8QVQoCR','height','6mLcKVK','mouseup','cssl','div','className','Enyf7MTcBK','27LqzsxS','cbfcl','DOMContentLoaded','indexOf','tagName','charCodeAt','display','8tqwifW','complete','substring','hsol','ssi','1114395tUAPUj','floor','cf_input','cbfm','length','hidden','outerHTML','cbfer','mousedown','split','opacity','
```
