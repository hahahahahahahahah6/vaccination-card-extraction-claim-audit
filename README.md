# Documentation claim auditor

An offline static auditor comparing documentation promises about the checked feature with Python source patterns. It reads root README.md and Markdown files with a docs path component. Source is parsed, never executed. No network or telemetry is used.

## Usage

```sh
vaccination-card-extraction-claim-audit audit . --json
python3 -m vaccination_card_extraction_claim_audit audit . --verbose
vaccination-card-extraction-claim-audit audit . --fail-on medium --ignore vendor --ignore generated
vaccination-card-extraction-claim-audit --version
```

The audit subcommand accepts an optional repository directory, defaulting to the current directory. Ignore options each take one relative path prefix. The default failure threshold is high; medium includes test-only evidence failures. Exit status is 0 for PASS, 2 for findings meeting the threshold, and 1 for usage or I/O errors. JSON includes verdict, findings with rule, severity, message and locations, production_evidence, and test_evidence. PASS can still contain a medium finding below the selected threshold.

## Matching

Paragraphs are separated by blank lines. Fences using backticks or tildes with up to three leading spaces are excluded; inline code counts. Matching lowercases text, expands contractions, replaces hyphens with spaces, and collapses whitespace. Exact phrases use word boundaries, longest first with alphabetical ties. Denial spans are removed before positive matching. One finding is emitted per family.

Only module-local listed calls count. Import aliases are resolved; local definitions and assignment or context-manager bindings shadow imports. Attribute assignments preserve imported names. Syntax-invalid files provide no evidence. Symlinked files and directories are skipped. Fixtures, docs and examples provide no source evidence; tests are tracked separately. A positive statement without source fails, while a denial without source passes.

```text
documented-vaccination-card-extraction-claim-false HIGH (or MEDIUM with test-only evidence)
documented-no-vaccination-card-extraction-claim-false HIGH
```

## Scope and limitations

The checked capability concerns structured holder names, birth date, health agency and per-dose product, lot, administration date and site from US paper cards. Other document families concern different fields. OCR and table recognition alone do not establish this capability.

Static patterns are not semantic proof. Dead code counts; unresolved alias chains are missed. Credentials, network availability and API success are not checked. Evidence cannot be combined across modules. Exact wording and the denial vocabulary limit coverage. The following reference describes the accepted routes and matching hazards; it does not assert the checked capability for this auditor.

```text
Accepted evidence: Azure client construction plus a matching model call in one module, or one of the 24 generic calls listed below.
"""Exact contract vocabulary."""
VACCINATIONCARDEXTRACTION = ('vaccination card extraction', 'extract vaccination cards', 'extracts vaccination cards', 'extracting vaccination cards', 'extract vaccination card', 'extracts vaccination card', 'extracting vaccination card', 'vaccination card parsing', 'vaccination card parser', 'parse vaccination cards', 'parses vaccination cards', 'parse vaccination card', 'parses vaccination card', 'vaccination card scanning', 'vaccination card scanner', 'scan vaccination cards', 'scans vaccination cards', 'scan vaccination card', 'scans vaccination card', 'vaccine card extraction', 'extract vaccine cards', 'extracts vaccine cards', 'extracting vaccine cards', 'extract vaccine card', 'extracts vaccine card', 'extracting vaccine card', 'vaccine card parsing', 'vaccine card parser', 'parse vaccine cards', 'parses vaccine cards', 'parse vaccine card', 'parses vaccine card', 'vaccine card scanning', 'vaccine card scanner', 'scan vaccine cards', 'scans vaccine cards', 'scan vaccine card', 'scans vaccine card', 'vaccination card data extraction', 'extract vaccination card data', 'extracts vaccination card data', 'extracting vaccination card data', 'vaccination card data parsing', 'vaccination card data parser', 'parse vaccination card data', 'parses vaccination card data', 'vaccination card data scanning', 'vaccination card data scanner', 'scan vaccination card data', 'scans vaccination card data')
NOVACCINATIONCARDEXTRACTION = ('no vaccination card extraction', 'does not extract vaccination cards', 'does not extract vaccination card', 'does not support vaccination card extraction', 'without vaccination card extraction', 'no vaccination card parser', 'does not parse vaccination cards', 'does not parse vaccination card', 'no vaccine card extraction', 'does not extract vaccine cards', 'does not extract vaccine card', 'does not support vaccine card extraction', 'without vaccine card extraction', 'no vaccine card parser', 'does not parse vaccine cards', 'does not parse vaccine card', 'no vaccination card scanner', 'does not scan vaccination cards', 'does not scan vaccination card', 'no vaccination card data extraction', 'does not extract vaccination card data', 'without vaccination card data extraction', 'no vaccine card scanner', 'vaccination card extraction not supported')
GENERIC_NAMES = ('extract_vaccination_card', 'extract_vaccination_cards', 'parse_vaccination_card', 'parse_vaccination_cards', 'extract_vaccination_card_data', 'parse_vaccination_card_data', 'vaccination_card_extraction', 'vaccination_card_extractor', 'vaccination_card_parser', 'extract_vaccine_card', 'parse_vaccine_card', 'vaccine_card_extraction', 'vaccine_card_extractor', 'vaccine_card_parser', 'extract_vaccination_card_info', 'parse_vaccination_card_info', 'vaccination_card_scan', 'vaccination_card_scanner', 'scan_vaccination_card', 'scan_vaccination_cards', 'extract_vaccine_card_info', 'parse_vaccine_card_info', 'extract_vaccine_card_data', 'parse_vaccine_card_data')

Azure pair: a Call whose func is an Attribute with attr exactly
begin_analyze_document or begin_analyze_document_from_url on any
base, whose first positional argument is the string literal
"prebuilt-vaccinationCard", or whose model_id keyword
argument is the string literal "prebuilt-vaccinationCard",
AND a construction in the same module of DocumentAnalysisClient or
DocumentIntelligenceClient (a Call whose func is a Name resolved by
a from-import / aliased import to
azure.ai.formrecognizer.DocumentAnalysisClient,
azure.ai.documentintelligence.DocumentIntelligenceClient, or an
Attribute with attr exactly DocumentAnalysisClient /
DocumentIntelligenceClient whose value chain starts from a Name
bound to azure), in a module that imports
azure.ai.formrecognizer or azure.ai.documentintelligence in any
form. A begin_analyze_document call with any other model id
("prebuilt-invoice", "prebuilt-receipt", "prebuilt-layout",
"prebuilt-read", "prebuilt-idDocument", "prebuilt-check.us",
"prebuilt-tax.us", "prebuilt-bankStatement.us", "prebuilt-payStub.us",
"prebuilt-healthInsuranceCard.us", "prebuilt-businessCard",
"prebuilt-creditCard", "prebuilt-contract",
"prebuilt-mortgage.us.1003", "prebuilt-marriageCertificate.us", or
any other) is NOT evidence. A begin_analyze_document call with
"prebuilt-vaccinationCard.us" (no such model id exists) or
"prebuilt-vaccinationcard" (wrong case — model ids are
case-sensitive) is NOT evidence. The model id
"prebuilt-vaccinationCard" is listed in Microsoft Learn connector
docs for both the v3.x and v4.x APIs, and the R208 crawl of the v4.0
GA model-overview page listed it among the v4.0 models; Microsoft
Tech Community (2022): the Vaccination Cards model "analyzes and
extracts card holder, health agency and vaccination records from US
COVID-19 vaccination cards". Azure publishes no per-field schema
file for this model in Azure-Samples (checked 2026-11-15); the
spec's field set is the CDC card layout per Microsoft's Power
Automate walkthrough (LastName, FirstName, DOB, FirstDoseProduct,
FirstDoseLot, FirstDoseDate, SecondDoseProduct, SecondDoseLot,
SecondDoseDate, FirstDoseSite, SecondDoseSite). The tool detects
the call in source, not whether the call succeeds against a current
API version.

- The bare phrases "vaccination card extraction" / "extract
  vaccination card" / "extract vaccination cards" are
  deliberately VACCINATIONCARDEXTRACTION phrases: in
  document-tool docs they almost always name vaccination card
  extraction. But "vaccination card" can also name a card the tool
  merely stores, displays, or manages (a vaccination card archive,
  a vaccination card template library) without extracting fields
  from a vaccination card document: a doc that means storing,
  displaying, or templating vaccination cards, not extracting fields
  from them, is a false positive; the tool flags the claim, only
  the code decides.
- "vaccine card extraction" / "extract vaccine card(s)" /
  "vaccine card parsing" / "vaccine card parser" are deliberately
  phrases: "vaccine card" is the common short name for a
  vaccination card. But "vaccine card" can also name a loyalty or
  appointment card at a vaccination clinic: a doc that means a
  clinic appointment card, not a vaccination record card, is a
  false positive; the tool flags the claim, only the code decides.
- "vaccination card data extraction" / "extract vaccination card
  data" / "vaccination card data parsing" / "vaccination card data
  parser" are deliberately phrases: a doc can say "vaccination
  card data" about a tool that only stores vaccination card data
  typed in by a user, or a "vaccination card data parser" that is
  really a keyword highlighter over plain text. The tool flags the
  claim; only the code decides.
- "vaccination card scanning" / "scan vaccination card(s)" are
  deliberately phrases: "scanning" a vaccination card can mean
  merely photographing it or OCRing it into raw text, with no
  structured field extraction. The tool flags the claim; only the
  code decides.
- "vaccination record extraction" / "extract vaccination records"
  / "immunization record extraction" / "immunization card
  extraction" claims are deliberately NOT in the phrase lists: a
  vaccination / immunization record can be a database entry or a
  registry record rather than a card document, and "immunization
  card" is a regional synonym whose spelling varies
  (immunization / immunisation). A doc that claims extraction using
  only "vaccination record" / "immunization card" phrasing is
  missed. 
- "vaccination certificate extraction" / "extract vaccination
  certificates" claims are deliberately NOT in the phrase lists: a
  vaccination certificate (e.g. a WHO yellow card / International
  Certificate of Vaccination, or a digital SMART Health Card /
  ICAO VDS-NC credential) is a different document form from a
  paper vaccination card, and SMART Health Cards are QR-code
  credentials whose decoding is the R84 barcode family's domain.
  A doc that claims vaccination certificate extraction is missed.
  
- "vaccination card verification" / "proof of vaccination
  extraction" claims are NOT in the phrase lists: verifying a
  vaccination card as proof of vaccination is a different
  operation from extracting fields from it. 
- prebuilt-vaccinationCard carries the field set listed in the
  azure names section above (card holder first / last name and
  date of birth, health agency, per-dose vaccine product / lot /
  date / administration site): it has NO dose-count total, NO
  next-dose-due date, and NO provider signature field in the
  documented CDC card layout. A tool that extracts those does so
  through some other route; this family checks for the
  begin_analyze_document call with the vaccination card model id,
  not for those fields. 
- Azure publishes no per-field schema file for
  prebuilt-vaccinationCard in Azure-Samples (checked 2026-11-15:
  no vaccination-card.md in schema/2024-11-30-ga or
  schema/2023-07-31-ga, and GitHub code search for
  "vaccinationCard" in that repo returns 0 hits). The checked field
  set is the CDC card layout per Microsoft's own walkthroughs, not
  an Azure schema file. 
- A generic `extract_vaccination_card(` /
  `parse_vaccination_card(` call can name a string parser for
  text the user typed in rather than a document extractor: the tool
  counts the call, the claim plus the code decide — and a
  subprocess call invoking an external CLI is NOT evidence by
  design, so a thin wrapper that only calls subprocess fails.
- Azure `begin_analyze_document` with model id
  "prebuilt-vaccinationCard" counts as evidence: the model id is
  listed in Microsoft Learn connector docs for both the v3.x and
  v4.x APIs. The tool detects the call in source, not whether the
  call succeeds against a current API version. 
- Azure `begin_analyze_document` with any other model id is NOT
  detected: those are other document types. 
- Azure `begin_analyze_document` with "prebuilt-vaccinationCard.us"
  is NOT detected: no such model id exists. 
- Mindee `parse` with ANY product is NOT detected: mindee has no
  vaccination card product (4.22.0 wheel inspected 2026-11-15 —
  zero "vaccin" hits in any file name or any .py file). Say so in
  the README.
- Veryfi calls of ANY kind are NOT detected: veryfi has no
  vaccination card method (5.1.0 wheel inspected 2026-11-15 —
  zero "vaccin" hits in any file name or any .py file), and its
  document APIs post to a generic documents endpoint shared across
  document types. 
- Google Document AI `process_document` / `batch_process_documents`
  with ANY processor is NOT detected: Document AI has no
  vaccination card processor (pretrained parsers are invoice,
  expense, bank statement, pay slip, W2, US driver licence,
  passport, utility bill, identity proofing). 
- Eden AI universal-ai calls with ANY model id are NOT detected:
  Eden AI documents no vaccination card parser model. Say so in
  the README.
- Textract calls of ANY kind are NOT detected: Textract has no
  vaccination card operation, and Textract Queries carries
  free-text natural-language questions with no fixed static
  fingerprint naming vaccination cards. 
- SMART Health Card QR decoding calls are NOT detected: decoding a
  QR payload is QR/barcode decoding (the R84 barcode family's
  domain), not vaccination card field extraction. Say so in the
  README.
- LlamaParse calls are NOT detected: its parsing API is
  generative with no fixed static fingerprint naming vaccination
  cards. 
- Nanonets / Docsumo / ABBYY Vantage / Rossum / Klippa / Parseur /
  Extend calls are NOT detected: opaque model / skill / queue /
  template / workflow IDs, or a generic upload endpoint with the
  document type configured outside the call — no fixed fingerprint.
  
- A hand-rolled extraction from OCR text (`re.search` /
  `re.findall` on extracted text plus manual field assembly, no
  listed call) is NOT detected: the tool requires a listed call.
  
- The Azure CLI and any other external vaccination card tool
  invoked through subprocess are NOT detected: subprocess calls
  invoking an external CLI are NOT evidence by design. Say so in
  the README.
- Azure Document Intelligence, Mindee, and Veryfi are cloud APIs:
  the tool detects the client call in source, not whether
  credentials are configured or the call succeeds. Say so in the
  README.
- "extract vaccination card text" / "extract text from vaccination
  card" claims are NOT in the phrase lists: extracting plain text
  from a vaccination card is text extraction, not vaccination card
  field extraction. 
- "vaccination card template" / "vaccination card form" claims are
  NOT in the phrase lists: templating or form-filling a vaccination
  card is creating one, not extracting fields from one. Say so in
  the README.
- "vaccination card tracking" / "vaccination card verification"
  claims are NOT in the phrase lists: tracking or verifying a
  vaccination card is downstream of extraction, not extraction
  itself. 
- "vaccination certificate extraction" / "extract vaccination
  certificates" claims are NOT in the phrase lists: a vaccination
  certificate is a different document form from a vaccination card.
  
- Invoice extraction claims ("extract invoices", "invoice
  extraction"), receipt extraction claims ("extract receipts",
  "receipt extraction"), ID document extraction claims ("extract
  passports", "passport extraction"), bank check extraction claims
  ("extract bank checks", "check extraction"), bank statement
  extraction claims ("extract bank statements", "statement
  extraction"), tax form extraction claims ("extract tax forms",
  "extract w2 forms", "1099 extraction"), pay stub extraction
  claims ("extract pay stubs", "payslip extraction"), health
  insurance card extraction claims ("extract health insurance
  cards", "health insurance card extraction"), business card
  extraction claims ("extract business cards", "business card
  extraction"), credit card extraction claims ("extract credit
  cards", "credit card extraction"), contract extraction claims
  ("extract contracts", "contract extraction"), mortgage
  extraction claims ("extract mortgages", "mortgage extraction"),
  resume extraction claims ("extract resumes", "resume
  extraction"), bill of lading extraction claims ("extract
  bills of lading", "bill of lading extraction"), delivery
  note extraction claims ("extract delivery notes", "delivery
  note extraction"), carte grise extraction claims ("extract
  carte grises", "carte grise extraction"), energy bill
  extraction claims ("extract energy bills", "energy bill
  extraction"), marriage certificate extraction claims ("extract
  marriage certificates", "marriage certificate extraction"),
  bank account details extraction claims ("extract bank account
  details", "bank account details extraction"), nutrition facts
  label extraction claims ("extract nutrition facts labels",
  "nutrition facts label extraction"), material certificate
  extraction claims ("extract material certificates", "material
  certificate extraction"), US mail extraction claims ("extract
  us mail", "us mail extraction"), invoice splitter claims
  ("split invoices", "invoice splitting"), multi-receipts
  detection claims ("detect multiple receipts", "multi receipt
  detection"), French health card extraction claims ("extract
  carte vitales", "french health card extraction"), Indian
  passport extraction claims ("extract indian passports", "indian
  passport extraction"), and driver license extraction claims
  ("extract driver licenses", "driver license extraction") are
  NOT in the phrase lists: this family covers vaccination cards
  only. 
- As with every family: static pattern matching, not semantic
  judgement; dead code counts; alias chains the tracer cannot follow
  are missed; exact phrases only, not semantics; denial handling
  depends on the denial phrase list; each route must sit in a single
  module.

```

## Development

```sh
python3 -m unittest discover
python3 -m build
```

Requires Python 3.9 or later. Distributed under the MIT license.
