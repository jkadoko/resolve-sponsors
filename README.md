# Biotech Sponsor Resolver v2

This project aims to resolve company names from the **AACT (Archive of Clinical Trials)** database to their corresponding **Stock Tickers** and **Market Data**.

## The Problem
The AACT database provides sponsor names (e.g., "Janssen, LP", "GEIGY Pharmaceuticals", "Merck Sharp & Dohme") as free-text strings. These names often do not match the official corporate entity names used in financial markets, making it difficult to link clinical trial data to stock performance.

## The Solution
The `resolve_sponsor.py` script matches these sponsor names to Wikidata entities to retrieve:
- **Official Company Name**
- **Stock Ticker** (e.g., JNJ, MRK, NVS)
- **Stock Exchange**
- **Wikidata URI** (for verifiable linking)

### Resolution Logic (v2)
1.  **Direct Linking**: Checks if the Clinical Trial (NCT ID) is already linked to a sponsor in Wikidata.
2.  **Smart Discovery**: Uses the Wikidata Search API with fuzzy matching:
    *   Strips suffixes (e.g., "GEIGY Pharmaceuticals" -> "GEIGY").
    *   **Historical Resolution**: Handles merged/acquired companies via `P1366` (Replaced By) and `P156` (Followed By) properties. For example, resolving "Wyeth" -> "Pfizer" or "Janssen" -> "Johnson & Johnson".
3.  **Parent Traversal**: Recursively traverses the corporate hierarchy (`P749`) to find the **Public Parent Company**. If a company is a private subsidiary, it walks up the ownership chain until it finds a public entity.

## Usage

### Prerequisites
- Python 3.x
- `requests` library

### Running the Script
To resolve sponsors from the provided dataset:
```bash
python resolve_sponsor.py --sponsors-file data/sponsors.txt --output sponsors_resolved.csv
```

### Options
- `--limit <N>`: Process only the first N records (useful for testing).
- `--output <filename>`: Specify the output CSV file (default: `sponsors_resolved.csv`).

## Output Format
The script generates a CSV with the following columns:
- `nct_id`: The Clinical Trial ID.
- `company`: The resolved official company name.
- `ticker`: The stock ticker (or "Private/Unlisted").
- `exchange`: The stock exchange.
- `status`: Active or Inactive/Dissolved.
- `wikidata_uri`: The permanent Wikidata URI for the resolved entity.

## Data Source
Original data schema: [AACT Schema](https://aact.ctti-clinicaltrials.org/schema)
