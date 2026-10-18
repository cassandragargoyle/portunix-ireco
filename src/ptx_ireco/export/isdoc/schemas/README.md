# ISDOC schemas (vendored)

This directory contains the bundled ISDOC XML Schemas used by the
`ptx_ireco.export.isdoc.validator` module. The schemas are vendored
into the repository so the runtime does not need network access at
validation time and so the wheel ships a self-contained validator.

## Bundled versions

| Schema file | Source |
| ----------- | ------ |
| `isdoc-invoice-6.0.2.xsd` | <https://mv.gov.cz/isdoc/> |

The schema version is encoded in the filename, so no per-version
subdirectory is used. Multiple versions can coexist side-by-side
(e.g. `isdoc-invoice-6.0.2.xsd`, `isdoc-invoice-7.0.0.xsd`); the
`field_map.json` `isdoc_version` field selects which one the
validator loads.

> Note: ADR-0007 originally specified ISDOC **6.0.1**, but the
> upstream distribution at mv.gov.cz currently ships **6.0.2**. The
> namespace (`http://isdoc.cz/namespace/2013`) is unchanged between
> 6.0.1 and 6.0.2; only minor refinements differ. The bump and the
> single-file / no-subdirectory layout are recorded in the
> "Implementation amendments" section of ADR-0007.

## License & source

ISDOC schemas are distributed by the **Ministry of the Interior of
the Czech Republic (MVČR)**, which has held the license to the ISDOC
format and its trademark since 5 May 2021 (transferred from
*spolek ICT UNIE*).

Permission to use, copy, modify and distribute the schema and its
documentation is granted in perpetuity under the upstream license
header carried inside each XSD file:

> Permission to use, copy, modify and distribute this schema and its
> documentation for any purpose and without fee is hereby granted in
> perpetuity, provided that the above copyright notice and this
> paragraph appear in all copies. The copyright holders make no
> representation about the suitability of the schema for any
> purpose. It is provided "as is" without expressed or implied
> warranty.
>
> Neither the name of the SPIS, ICT UNIE, nor the name ISDOC may be
> used to endorse or promote products derived from this software
> without specific prior written permission.

## Background (verbatim, original Czech — source: mv.gov.cz/isdoc)

> Ministerstvo vnitra je držitelem licence k formátu ISDOC a její
> ochranné známky. Stalo se tak dne 5. května 2021 popisem smlouvy
> mezi Ministerstvem vnitra a stávajícím držitelem spolkem ICT UNIE.
>
> ISDOC (Information System Document) je formát elektronické
> fakturace v ČR, který definovala "Pracovní skupina pro Elektronické
> standardy výměny dat" sdružení SPIS. Dne 16. října 2008 byla
> podepsána "Deklarace o společném postupu v oblasti řešení
> elektronické fakturace v ČR". Tato deklarace vyjadřuje závazek
> jednotlivých výrobců ekonomických a ERP systémů (deklaraci
> podepsalo celkem 14 významných firem na trhu) vybudovat společný
> formát elektronické fakturace a do jednoho roku od jeho vyhlášení
> jej implementovat do svých komerčních řešení. Dalšími signatáři
> byli tehdejší zástupci státu, jmenovitě ministr financí Miroslav
> Kalousek a náměstek ministra vnitra Zdeněk Zajíček.
>
> Výrobci ekonomických a podnikových systémů tedy budou používat
> standardizovanou formu exportů a přijímání elektronických
> fakturačních zpráv, což umožní podnikům a institucím - uživatelům
> různých SW - mezi sebou vzájemně komunikovat.
>
> MVČR deklaruje, kromě závazku zařazení standardu ISDOC do
> systematiky standardů ISVS, svůj zájem na dalším rozvoji tohoto
> formátu elektronické fakturace. Formát či jeho další ztvárnění
> budou optimalizována i v souvislosti s jeho zařazením mezi tzv.
> výstupní datové formáty podle zákona č. 499/2004 Sb. o archivnictví
> a spisové službě, přičemž v rámci efektivního využití výstupního
> datového formátu bude navrženo také řešení kombinující výstupní
> datový formát PDF/A a ISDOC a to způsobem, zabezpečujícím co možná
> nejvyšší efektivitu zpracování, zejména pak při příjmu
> veřejnoprávními původci se snahou o maximální možnou automatizaci
> činností.

## Updating the bundled schemas

1. Download the new XSD from <https://mv.gov.cz/isdoc/>.
2. Place it directly under `schemas/` (the version is in the filename — no subdirectory needed).
3. Update `models/invoice/exports/isdoc/cze/field_map.json` (`isdoc_version`).
4. Re-run the validator unit tests; refresh golden snapshots if the new schema shifted any element ordering.
5. Document the bump in ADR-0007 (or a follow-up ADR if the namespace changed).
