# Biotech Sponsor Resolver v2

This project resolves company names from the **AACT (Archive of Clinical Trials)** database and **OpenFDA** drug product data to their corresponding **Stock Tickers** and **Market Data**.

## The Problem
Biotech data sources often use free-text strings for sponsor names (e.g., "Janssen, LP", "GEIGY Pharmaceuticals", "Bristol-Myers Squibb Company"). These names often do not match the official corporate entity names used in financial markets, making it difficult to link clinical trial or product data to stock performance.

## The Solution
This project provides two main scripts to resolve sponsors using **Wikidata**:

1.  **`resolve_products.py`**: Resolves a specific ticker to its products or a company name to its ticker.
2.  **`extract_openfda_products.py`**: Extracts products from the OpenFDA dataset and resolves their sponsors to tickers.
3.  **`resolve_sponsor.py`**: The core logic library for resolution (also runnable as a standalone script for AACT data).

### Core Resolution Logic
The resolution engine uses a multi-step approach:
1.  **Direct Linking**: Checks known identifiers.
2.  **Smart Discovery**: Uses Wikidata Search API with fuzzy matching and alias checking (`skos:altLabel`).
3.  **Historical Resolution**: Handles merged/acquired companies via `P1366` (Replaced By) and `P156` (Followed By) properties.
4.  **Parent Traversal**: Recursively traverses the corporate hierarchy (`P749`) to find the **Public Parent Company**.
5.  **Ticker Verification**: Validates candidates by checking for stock tickers (`P249`) or exchange listings (`P414`).

---

## 1. OpenFDA Product Extraction
**Script**: `extract_openfda_products.py`

Extracts commercial products and resolves their sponsors from the OpenFDA `drug-drugsfda` JSON dataset.

### Usage
```bash
python extract_openfda_products.py
```

### Options
-   `--filter <STRING>`: Process only sponsors containing this case-insensitive string (e.g., `--filter "BRISTOL"`).
-   `--limit <INT>`: Limit the number of unique sponsors processed (e.g., `--limit 10`).

### Output (`products.csv`)
Columns include:
-   `product_name`: Brand name (e.g., ELIQUIS).
-   `active_ingredients_name`: e.g., APIXABAN.
-   `active_ingredients_strength`: e.g., 2.5MG; 5MG.
-   `rxcui`: RxNorm Concept Unique Identifier.
-   `resolved_sponsor_name`: Resolved parent company.
-   `ticker`: Stock ticker (e.g., BMY).
-   `wikidata_uri`: URI for the resolved entity.

An `unresolved_sponsors.csv` file is also generated for debugging.

---

## 2. Ticker & Product Lookup
**Script**: `resolve_products.py`

Quickly look up a company's ticker or their known products from Wikidata.

### Usage
**Resolve Ticker from Name**:
```bash
python resolve_products.py --ticker "Novo Nordisk" 
# Output: Found company: Novo Nordisk A/S (NVO)
```

**Get Products for Ticker**:
```bash
python resolve_products.py --ticker "NVO"
# Output: Lists products like Ozempic, Wegovy, etc.
```

---

## 3. General Sponsor Resolution
**Script**: `resolve_sponsor.py`

Resolves a list of sponsor names from a file (legacy/AACT mode).

### Usage
```bash
python resolve_sponsor.py --sponsors-file data/sponsors.txt --output sponsors_resolved.csv
```

---

## Prerequisites
-   Python 3.x
-   Dependencies: `requests`, `ijson`

Install dependencies:
```bash
pip install -r requirements.txt
```

## Data Source
-   **OpenFDA**: [`drug-drugsfda.json`](https://open.fda.gov/apis/drug/drugsfda/download/)
-   **Wikidata**: Live SPARQL and API access.
