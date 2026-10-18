# portunix-ireco

*Další jazyky: [English](README.md) · [Slovenčina](README.sk.md)*

## Přehled

`portunix-ireco` rozšiřuje [portunix-reco](https://github.com/CassandraGargoyle/portunix-reco) o vytěžování
dokumentů pomocí flexibilních rozvržení (flexylayouts). Je určen pro zpracování polostrukturovaných
dokumentů, převážně strojově tištěných — včetně strojově vyplněných formulářů.

### Co se přebírá z `portunix-reco`

Deklarováno jako závislost na `ptx-reco>=0.3.4` (`pyproject.toml`).

- **VIM parser (PDF → VIM dokument)** — krok `parse` v
  `src/ptx_ireco/pipeline/parse.py` spouští z `ptx_reco.vim`
  `ExecutionEngine` + `PluginRegistry` s `TextBlockExtractorPlugin`
  a volitelně barcode / table / graphics / toc / metadata extraktory.
  Sémantický krok `extract` (flexylayouts) je už čistě ireco.
- **Chybové kódy worker tasku** — `src/ptx_ireco/worker/task/errors.py`
  re-exportuje `ptx_reco.worker.task.errors`, aby formát
  TaskRequest/TaskResponse byl identický mezi `ptx-reco-worker`
  a `ptx-ireco-worker`.
- **Vzor rozdělení na worker + watcher plugin** — uspořádání manifestů
  (`plugin-worker.json` / `plugin-watcher.json`) a struktura modulů
  následují konvenci zavedenou v `portunix-reco` (viz
  [ADR-0005](docs/adr/0005-ireco-plugin-split.md)).

## Informace o projektu

- **GitHub repozitář**: <https://github.com/cassandragargoyle/portunix-ireco>
- **Issues**: <https://github.com/cassandragargoyle/portunix-ireco/issues>
- **Název projektu**: portunix-ireco

## Začínáme

TODO: Doplnit popis projektu a pokyny k instalaci

### OCR pro skenované PDF (issue 007)

Skenované (image-only) faktury, kde pdfplumber nenajde žádnou textovou
vrstvu, lze obnovit volitelným per-stránkovým OCR krokem v `parse`.
Před spuštěním Tesseractu se každá stránka zkontroluje proti
**ink-ratio bráně** (defaultně 0,5 % ne-bílých pixelů po Otsu
binarizaci), aby se OCR nepouštělo na prázdné skeny.

```bash
ptx-ireco parse scan.pdf -o scan.vim.json --ocr --ocr-language eng+ces
```

Vyžaduje `tesseract` binárku, jazyková data a `pdf2image` + Poppler.
Detaily a všechny `--ocr*` přepínače viz
[`docs/cli/parse.md`](docs/cli/parse.md).

### Export do ISDOC (issue 006 / [ADR-0007](docs/adr/0007-isdoc-export.md))

Pro integraci s českými ERP systémy umí ireco převést populovaný
`*.vim.json` do **ISDOC 6.0.2** — buď jako prosté XML (`*.isdoc`),
nebo jako `*.isdocx` ZIP balík s vloženým původním PDF. JSON sidecar
s provenience (`*.isdoc.provenance.json`) mapuje každý emitovaný
XPath zpět na zdrojový blok v PDF — audit trail tak přežije export.
Export je volitelný třetí krok pipeline (parse → extract →
**export**) a je k dispozici i jako worker task
`ireco.invoice.export` a opt-in watcher post-processor
(`watcher.post_process: ["export-isdoc"]`).

```bash
ptx-ireco export samples/invoice/flowii-FA_26050001.pdf.vim.json \
    --format isdoc --profile standard
```

Detaily, profily a validační brány viz
[`docs/cli/export.md`](docs/cli/export.md).

## Dokumentace

Vývojářské pokyny viz [docs/contributing/](docs/contributing/).

## Licence

MIT — viz [LICENSE](LICENSE).
