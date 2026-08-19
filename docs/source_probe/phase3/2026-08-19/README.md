# Phase 3 source discovery

- Probe run (UTC): `2026-08-19T00:47:18.735991+00:00`

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

## `bis` — Bank for International Settlements

Debt securities statistics by residence, sector and maturity. The brief names it first for cross-sovereign comparability.

### `https://stats.bis.org/api/v1/dataflow/BIS`

- HTTP 200, `application/xml;charset=UTF-8`, 15,287 bytes

```
<?xml version="1.0" ?><mes:Structure xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:mes="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:str="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:com="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"><mes:Header><mes:ID>IDREF71a0638e-0cdd-4d33-ab26-e22e3e1e2086</mes:ID><mes:Test>false</mes:Test><mes:Prepared>2026-08-18T14:11:17Z</mes:Prepared><mes:Sender id="UNKNOWN"></mes:Sender><mes:Receiver id="not_supplied"></mes:Receiver></mes:Header><mes:Structures><str:Dataflows><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=BIS:BIS_REL_CAL(1.0)" isExternalReference="false" agencyID="BIS" id="BIS_REL_CAL" isFinal="false" version="1.0"><com:Name xml:lang="en">BIS_RELEASE_CALENDAR</com:Name><str:Structure><Ref package="datastructure" agencyID="BIS" id="BIS_RELEASE_CALENDAR" version="1.0" class="DataStructure"></Ref></str:Structure></str:Dataflow><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=BIS:WS_CBPOL(1.0)" isExternalReference="false" agencyID="BIS" id="WS_CBPOL" isFinal="false" version="1.0"><com:Name xml:lang="en">Central bank policy rates</co
```

### `https://stats.bis.org/api/v1/dataflow`

- HTTP 200, `application/xml;charset=UTF-8`, 16,687 bytes

```
<?xml version="1.0" ?><mes:Structure xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:mes="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:str="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:com="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"><mes:Header><mes:ID>IDREF6e3e8dca-0b56-4740-a956-db1dfa155f93</mes:ID><mes:Test>false</mes:Test><mes:Prepared>2026-08-18T10:22:13Z</mes:Prepared><mes:Sender id="UNKNOWN"></mes:Sender><mes:Receiver id="not_supplied"></mes:Receiver></mes:Header><mes:Structures><str:Dataflows><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=BIS:BIS_REL_CAL(1.0)" isExternalReference="false" agencyID="BIS" id="BIS_REL_CAL" isFinal="false" version="1.0"><com:Name xml:lang="en">BIS_RELEASE_CALENDAR</com:Name><str:Structure><Ref package="datastructure" agencyID="BIS" id="BIS_RELEASE_CALENDAR" version="1.0" class="DataStructure"></Ref></str:Structure></str:Dataflow><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=BIS:WS_CBPOL(1.0)" isExternalReference="false" agencyID="BIS" id="WS_CBPOL" isFinal="false" version="1.0"><com:Name xml:lang="en">Central bank policy rates</co
```

### `https://www.bis.org/statistics/index.htm`

- HTTP 200, `text/html; charset=UTF-8`, 55,523 bytes
- redirected to `https://www.bis.org/statistics/dataportal/index.htm`

```
<!DOCTYPE html>
<html class='no-js' lang='en' xml:lang='en' xmlns='http://www.w3.org/1999/xhtml'>
<head>
<meta content='IE=edge' http-equiv='X-UA-Compatible'>
<meta content='width=device-width, initial-scale=1.0' name='viewport'>
<meta content='text/html; charset=utf-8' http-equiv='Content-Type'>
<meta content='About BIS statistics' property='og:title'>
<meta content='https://www.bis.org/statistics/dataportal/index.htm' property='og:url'>
<link href='https://www.bis.org/statistics/dataportal/index.htm' rel='canonical'>
<meta content='https://www.bis.org/img/bislogo_og.jpg' property='og:image'>
<meta content='summary_large_image' name='twitter:card'>
<meta content='@bis_org' name='twitter:site'>
<meta content='' name='keywords'>
<meta content='Mon, 22 Jan 2024 07:54:00 +0000' http-equiv='Last-Modified'>
<title>About BIS statistics</title>
<link rel="icon" type="image/x-icon" href="/favicon-570124710617266452aaee59dc8fe89474345158607e5dd372d3f5389925fe99.ico" />
<link rel="shortcut icon" type="image/x-icon" href="/favicon-570124710617266452aaee59dc8fe89474345158607e5dd372d3f5389925fe99.ico" />
<link rel="stylesheet" href="/bis_original/bis/bis-262d81e317cbfa091209278241285c98d68fd010
```

## `ecb` — European Central Bank

Securities issues statistics and government finance statistics cover Germany, France and Italy on one basis, which is three of the five Phase 3 sovereigns from a single publisher.

### `https://data-api.ecb.europa.eu/service/dataflow/ECB`

- HTTP 200, `application/vnd.sdmx.structure+xml;version=2.1`, 39,226 bytes

```
<?xml version='1.0' encoding='UTF-8'?><mes:Structure xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xml="http://www.w3.org/XML/1998/namespace" xmlns:mes="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:str="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:com="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"><mes:Header><mes:ID>IREF004401</mes:ID><mes:Test>false</mes:Test><mes:Prepared>2026-08-19T00:47:20Z</mes:Prepared><mes:Sender id="Unknown"/><mes:Receiver id="not_supplied"/></mes:Header><mes:Structures><str:Dataflows><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=ECB:AGR(1.0)" isExternalReference="false" agencyID="ECB" id="AGR" isFinal="false" version="1.0"><com:Name xml:lang="en">AGR</com:Name><str:Structure><Ref package="datastructure" agencyID="ECB" id="ECB_BCS1" version="1.0" class="DataStructure"/></str:Structure></str:Dataflow><str:Dataflow urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=ECB:AME(1.0)" isExternalReference="false" agencyID="ECB" id="AME" isFinal="false" version="1.0"><com:Name xml:lang="en">AMECO</com:Name><str:Structure><Ref package="datastructure" agencyID="ECB" id="EC
```

### `https://data-api.ecb.europa.eu/service/data/SEC?lastNObservations=1&format=jsondata`

- HTTP 200, `application/vnd.sdmx.data+json;version=1.0.0-wd`, 17,922,888 bytes
- JSON top-level keys: `['dataSets', 'header', 'structure']`

```
{"header":{"id":"19930675-7f94-4826-9abf-8cbe23a6f18e","test":false,"prepared":"2026-08-19T02:47:36.771+02:00","sender":{"id":"ECB"}},"dataSets":[{"action":"Replace","validFrom":"2026-08-19T02:47:36.771+02:00","series":{"0:0:0:0:0:0:0:0:0":{"attributes":[0,null,0,null,null,null,null,null,null,null,null,null,0,null,null,0,0,0,0],"observations":{"0":[9486.04,0,0,null,null]}},"0:0:0:0:0:0:1:0:0":{"attributes":[0,null,0,null,null,null,null,null,null,null,null,null,0,null,null,1,1,0,0],"observations":{"0":[22566.539999999997,0,0,null,null]}},"0:0:0:0:0:0:2:1:0":{"attributes":[0,null,0,null,null,null,null,null,null,null,null,null,0,null,null,0,2,1,0],"observations":{"0":[16388.475304223335,0,0,null,null]}},"0:0:0:0:0:0:2:0:0":{"attributes":[0,null,0,null,null,null,null,null,null,null,null,null,0,null,null,0,3,0,0],"observations":{"0":[32052.58,0,0,null,null]}},"0:0:0:0:0:0:3:0:0":{"attributes":[0,null,0,null,null,null,null,null,null,null,null,null,0,null,null,0,4,0,0],"observations":{"0":[0,0,0,null,null]}},"0:0:0:0:0:1:0:0:0":{"attributes":[0,null,1,null,null,null,null,null,null,null,null,null,0,null,null,2,5,0,0],"observations":{"0":[4108.8,0,0,null,null]}},"0:0:0:0:0:1:1:0:0":{"attrib
```

## `eurostat` — Eurostat

Government debt by instrument and maturity (gov_10q_ggdebt), quarterly, harmonised across member states.

### `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT`

- HTTP 200, `application/vnd.sdmx.structure+xml;version=2.1`, 37,200,409 bytes

```
<?xml version="1.0" encoding="UTF-8"?>
<m:Structure xmlns:m="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:s="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:c="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"><m:Header><m:ID>DF1787086808</m:ID><m:Test>false</m:Test><m:Prepared>2026-08-18T23:00:08.07+02:00</m:Prepared><m:Sender id="ESTAT"/></m:Header><m:Structures><s:Dataflows><s:Dataflow id="LFSQ_EPGAN21" urn="urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=ESTAT:LFSQ_EPGAN21(1.0)" agencyID="ESTAT" version="1.0" isFinal="false"><c:Annotations><c:Annotation><c:AnnotationTitle>DATASET</c:AnnotationTitle><c:AnnotationType>DISSEMINATION_OBJECT_TYPE</c:AnnotationType></c:Annotation><c:Annotation><c:AnnotationTitle>131337</c:AnnotationTitle><c:AnnotationType>OBS_COUNT</c:AnnotationType></c:Annotation><c:Annotation><c:AnnotationTitle>2026-Q1</c:AnnotationTitle><c:AnnotationType>OBS_PERIOD_OVERALL_OLDEST</c:AnnotationType></c:Annotation><c:Annotation><c:AnnotationTitle>2026-Q1</c:AnnotationTitle><c:AnnotationType>OBS_PERIOD_OVERALL_LATEST</c:AnnotationType></c:Annotation><c:Annotation><c:AnnotationTitle>2026-06-12T08:02:48+0200</c:Annotat
```

### `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10q_ggdebt?format=JSON&lang=EN`

- HTTP 200, `application/json`, 12,005,836 bytes
- JSON top-level keys: `['class', 'dimension', 'extension', 'id', 'label', 'size', 'source', 'status', 'updated', 'value', 'version']`

```
{"version":"2.0","class":"dataset","label":"Quarterly government debt","source":"ESTAT","updated":"2026-07-21T11:00:00+0200","value":{"7408":0.0,"7409":0.0,"7410":0.0,"7411":0.0,"7412":0.0,"7413":0.0,"7414":0.0,"7415":0.0,"7416":0.0,"7417":0.0,"7418":0.0,"7419":0.0,"7420":0.0,"7421":0.0,"7422":0.0,"7423":0.0,"7424":0.0,"7425":0.0,"7426":0.0,"7427":0.0,"7428":0.0,"7429":0.0,"7430":0.0,"7431":0.0,"7432":0.0,"7433":0.0,"7434":0.0,"7435":0.0,"7436":0.0,"7437":0.0,"7438":0.0,"7439":0.0,"7440":0.0,"7441":0.0,"7442":0.0,"7443":0.0,"7444":0.0,"7445":0.0,"7446":0.0,"7447":0.0,"7448":0.0,"7449":0.0,"7450":0.0,"7451":0.0,"7452":0.0,"7453":0.0,"7454":0.0,"7455":0.0,"7456":0.0,"7457":0.0,"7458":0.0,"7459":0.0,"7460":0.0,"7461":0.0,"7462":0.0,"7463":0.0,"7464":0.0,"7465":0.0,"7466":0.0,"7467":0.0,"7468":0.0,"7469":0.0,"7470":0.0,"7471":0.0,"7472":0.0,"7473":0.0,"7474":0.0,"7475":0.0,"7476":0.0,"7477":0.0,"7478":0.0,"7479":0.0,"7480":0.0,"7481":0.0,"19503":0.0,"19504":0.0,"19505":0.0,"19506":0.0,"19507":0.0,"19508":0.0,"19509":0.0,"19510":0.0,"19511":395.0,"19512":380.0,"19513":415.0,"19514":451.0,"19515":478.0,"19516":515.0,"19517":538.0,"19518":576.0,"19519":587.0,"19520":614.0,"19521":647.0,"1
```

## `france_aft` — Agence France Trésor

OAT and BTF issuance and outstanding.

### `https://www.aft.gouv.fr/en`

- HTTP 200, `text/html; charset=UTF-8`, 77,749 bytes

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

- HTTP 200, `text/html; charset=utf-8`, 224,829 bytes

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

- HTTP 200, `text/html;charset=UTF-8`, 674,136 bytes

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

- HTTP 200, `text/html`, 46,460 bytes
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
  <meta name="date" content="2026-07-29" />

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

### `https://sdmx.oecd.org/public/rest/dataflow/OECD`

- **http_error**: `404`

### `https://sdmx.oecd.org/public/rest/dataflow`

- HTTP 200, `application/vnd.sdmx.structure+xml; charset=utf-8; version=2.1`, 8,880,148 bytes

```
<?xml version="1.0" encoding="utf-8"?>
<!--NSI Web Service v8.19.8.0-->
<message:Structure xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message" xmlns:structure="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure" xmlns:common="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common">
  <message:Header>
    <message:ID>IDREF14798</message:ID>
    <message:Test>false</message:Test>
    <message:Prepared>2026-08-19T02:48:22.96667+02:00</message:Prepared>
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
        <structure:Stru
```

## `uk_dmo` — UK Debt Management Office

Gilt and Treasury bill issuance, per-security detail. The UK is the closest analogue to the US data estate.

### `https://www.dmo.gov.uk`

- HTTP 200, `text/html; charset=utf-8`, 33,337 bytes
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

- HTTP 200, `text/html; charset=UTF-8`, 15,238 bytes
- redirected to `https://validate.perfdrive.com/5e975472fcf167bd1130d74f0fb9a2f7/?ssa=ffb235b9-b168-4155-85c1-44a58c25d149&ssb=62912235001&ssc=https%3A%2F%2Fwww.dmo.gov.uk%2Fdata%2F&ssi=eba9b40b-bhbz-4c1d-a28c-a80fe40ed3f9&ssk=support@shieldsquare.com&ssm=84319327194868477109129305202755&ssn=dc14a05daf9ec1c9b5053a6746e9f6c16d33ddce4a44-5681-4105-8fe3d8&sso=93ff11a5-bf5e4a77e856315847507d77921da0946a5b67004690737d&ssp=86200988001787135517178718746151956&ssq=82083090050519495085600505288062754327894&ssr=NDAuNzYuMjM5LjE4&sst=python-requests/2.33.1&ssu=&ssv=&ssw=&ssx=eyJfX3V6bWYiOiI3ZjkwMDBkZGNlNGE0NC01NjgxLTQxMDUtODFhNS1iZjVlNGE3N2U4NTYxLTE3ODcxMDA1MDUxNTEwLTAwNDNmNTg5ODI2YWYzYWZlYmQxMCIsInJkIjoiZG1vLmdvdi51ayIsInV6bXgiOiI3ZmMwMDBlYzg5Yzg0Yy1hMzRkLTQxNDYtYTQ4OC0zYzkyMDU0ODZkZDcxLTE3ODcxMDA1MDUxNTEwLTAwMTdhY2UyMGM2ZGNjOTVmZTgxMCJ9`

```
<head><title>ShieldSquare Captcha</title><script type="text/javascript">
	window.SSJSInternal = 18155;

	var __uzdbm_1 = "ddce4a44-5681-4105-81a5-bf5e4a77e856";
	var __uzdbm_2 = "ZWJhOWI0MGItYmhiei00YzFkLWEyOGMtYTgwZmU0MGVkM2Y5JDQwLjc2LjIzOS4xOA==";
	
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
function _0x147a(){var _0x2ec979=['ecb5e100e5a9a3e7f6d1fd97512215282','mousemove','toGMTString','0xcvd','1976572igpWBa','touches','1993290amMtaY','block','2128497rXvxFu','Udr9HvhYUw','getTime','style','parentElement','5876928iktpYv',';\x20path=/','8QVQoCR','height','6mLcKVK','mouseup','cssl','div','className','Enyf7MTcBK','27LqzsxS','cbfcl','DOMContentLoaded','indexOf','tagName','charCodeAt','display','8tqwifW','complete','substring','hsol','ssi','1114395tUAPUj','floor','cf_input','cbfm','length','hidden','outerHTML','cbfer','mousedown','split','opacity','8360
```
