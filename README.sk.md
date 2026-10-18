# portunix-ireco

*Ďalšie jazyky: [English](README.md) · [Čeština](README.cs.md)*

## Prehľad

`portunix-ireco` rozširuje [portunix-reco](https://github.com/CassandraGargoyle/portunix-reco) o vyťažovanie
dokumentov pomocou flexibilných rozložení (flexylayouts). Je určený na spracovanie pološtruktúrovaných
dokumentov, prevažne strojovo tlačených — vrátane strojovo vyplnených formulárov.

### Čo sa preberá z `portunix-reco`

Deklarované ako závislosť na `ptx-reco>=0.3.4` (`pyproject.toml`).

- **VIM parser (PDF → VIM dokument)** — krok `parse` v
  `src/ptx_ireco/pipeline/parse.py` spúšťa z `ptx_reco.vim`
  `ExecutionEngine` + `PluginRegistry` s `TextBlockExtractorPlugin`
  a voliteľne barcode / table / graphics / toc / metadata extraktory.
  Sémantický krok `extract` (flexylayouts) je už čisto ireco.
- **Chybové kódy worker tasku** — `src/ptx_ireco/worker/task/errors.py`
  re-exportuje `ptx_reco.worker.task.errors`, aby formát
  TaskRequest/TaskResponse bol identický medzi `ptx-reco-worker`
  a `ptx-ireco-worker`.
- **Vzor rozdelenia na worker + watcher plugin** — usporiadanie manifestov
  (`plugin-worker.json` / `plugin-watcher.json`) a štruktúra modulov
  nasledujú konvenciu zavedenú v `portunix-reco` (pozri
  [ADR-0005](docs/adr/0005-ireco-plugin-split.md)).

## Informácie o projekte

- **GitHub repozitár**: <https://github.com/cassandragargoyle/portunix-ireco>
- **Issues**: <https://github.com/cassandragargoyle/portunix-ireco/issues>
- **Názov projektu**: portunix-ireco

## Začíname

TODO: Doplniť popis projektu a pokyny na inštaláciu

### OCR pre skenované PDF (issue 007)

Skenované (image-only) faktúry, kde pdfplumber nenájde žiadnu textovú
vrstvu, je možné obnoviť voliteľným per-stránkovým OCR krokom v `parse`.
Pred spustením Tesseractu sa každá stránka skontroluje voči
**ink-ratio bráne** (defaultne 0,5 % nebielych pixelov po Otsu
binarizácii), aby sa OCR nepúšťalo na prázdne skeny.

```bash
ptx-ireco parse scan.pdf -o scan.vim.json --ocr --ocr-language eng+ces+slk
```

Vyžaduje `tesseract` binárku, jazykové dáta a `pdf2image` + Poppler.
Detaily a všetky `--ocr*` prepínače pozri v
[`docs/cli/parse.md`](docs/cli/parse.md).

### Export do ISDOC (issue 006 / [ADR-0007](docs/adr/0007-isdoc-export.md))

Pre integráciu s českými ERP systémami vie ireco previesť populovaný
`*.vim.json` do **ISDOC 6.0.2** — buď ako čisté XML (`*.isdoc`),
alebo ako `*.isdocx` ZIP balík s vloženým pôvodným PDF. JSON sidecar
s proveniencami (`*.isdoc.provenance.json`) mapuje každý emitovaný
XPath späť na zdrojový blok v PDF — audit trail tak prežije export.
Export je voliteľný tretí krok pipeline (parse → extract →
**export**) a je k dispozícii aj ako worker task
`ireco.invoice.export` a opt-in watcher post-processor
(`watcher.post_process: ["export-isdoc"]`).

```bash
ptx-ireco export samples/invoice/flowii-FA_26050001.pdf.vim.json \
    --format isdoc --profile standard
```

Podrobnosti, profily a validačné brány pozri v
[`docs/cli/export.md`](docs/cli/export.md).

## Dokumentácia

Vývojárske pokyny pozri [docs/contributing/](docs/contributing/).

## Licencia

MIT — pozri [LICENSE](LICENSE).
