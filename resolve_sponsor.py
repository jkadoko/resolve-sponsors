import argparse
import csv
import sys
import time
import requests
from collections import defaultdict

# Use standard Wikidata SPARQL endpoint
QLEVER_ENDPOINT = "https://query.wikidata.org/sparql"
# Standard User-Agent for Wikidata policy
HEADERS = {"User-Agent": "BiotechAnalyzer/1.0 (contact@example.com)"}

def _run_sparql_query(query: str, purpose: str):
    """
    Helper to run SPARQL query with retries and timeout.
    """
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.get(
                QLEVER_ENDPOINT,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=60
            )
            response.raise_for_status()
            return response.json()["results"]["bindings"]
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Query ({purpose}) failed (Attempt {attempt+1}/{max_retries}): {e}. Retrying in {retry_delay}s...", file=sys.stderr)
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                error_msg = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f"\nResponse: {e.response.text}"
                print(f"Error querying ({purpose}) after {max_retries} attempts: {error_msg}", file=sys.stderr)
                return None
    return None

def get_trial_primary_sponsor(nct_id: str):
    """
    Stage 1: Lightweight Identity Query.
    Finds the company URI and label associated with the NCT ID.
    """
    query = f"""
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?trialLabel ?company ?companyLabel WHERE {{
        ?trial wdt:P3098 "{nct_id}" ;
               rdfs:label ?trialLabel .
        
        OPTIONAL {{ ?trial wdt:P859 ?company . }}
        
        FILTER (lang(?trialLabel) = "en")
        
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
        }}
    }}
    LIMIT 1
    """
    
    rows = _run_sparql_query(query, f"Identity-{nct_id}")
    if not rows:
        return {"nct_id": nct_id, "trial_label": "Unknown", "company_uri": None, "company_label": None}
    
    row = rows[0]
    return {
        "nct_id": nct_id,
        "trial_label": row.get("trialLabel", {}).get("value", "Unknown"),
        "company_uri": row.get("company", {}).get("value"),
        "company_label": row.get("companyLabel", {}).get("value")
    }

def enrich_company_content(company_uri: str, company_label: str):
    """
    Stage 2: Enrichment Query.
    Fetches details for a specific company URI using recursive parent traversal.
    """
    if not company_uri:
        return {}

    company_qid = company_uri.split("/")[-1]
    
    # Improved Traversal: P749 (Parent Org) only, excluding P127 (Shareholder)
    query = f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT
        ?currentName
        ?ticker
        ?exchangeLabel
        ?dissolved
    WHERE {{
        VALUES ?entity {{ wd:{company_qid} }}

        # Traverse hierarchy to find parent
        ?entity (wdt:P1366|wdt:P156|wdt:P749)* ?currentEntity.
        
        FILTER NOT EXISTS {{ ?currentEntity wdt:P1366 ?futureReplacement. }}

        ?currentEntity rdfs:label ?currentName.
        FILTER(LANG(?currentName) = "en")

        OPTIONAL {{ ?currentEntity wdt:P249 ?directTicker. }}
        
        OPTIONAL {{ 
            ?currentEntity p:P414 ?exchangeStatement. 
            ?exchangeStatement ps:P414 ?exchange.
            ?exchange rdfs:label ?exchangeLabel.
            FILTER(LANG(?exchangeLabel) = "en")
            OPTIONAL {{ ?exchangeStatement pq:P249 ?qualifierTicker. }}
        }}
        
        BIND(COALESCE(?directTicker, ?qualifierTicker) AS ?ticker)
        
        OPTIONAL {{ ?currentEntity wdt:P576 ?dissolved. }}
    }}
    ORDER BY DESC(?ticker) ASC(?dissolved)
    LIMIT 1
    """
    
    rows = _run_sparql_query(query, f"Enrich-{company_qid}") or []
    
    if not rows:
         # Fallback default if enrichment yields nothing
         return {
            "parents": set(),
            "subsidiaries": set(),
            "tickers": set(),
            "exchanges": set(),
            "countries": set(),
            "sec_cik": None,
            "dissolved": False
         }
         
    res = rows[0]
    # Remove debug print for production
    # print(f" [DEBUG Enrich: {company_qid} -> {res.get('currentName', {}).get('value')} | Ticker: {res.get('ticker', {}).get('value', 'None')}] ", end="")
    ticker = res.get('ticker', {}).get('value', "PRIVATE")
    status = "Active"
    if "dissolved" in res: status = "Dissolved"
    
    # Map back to the expected structure for existing CSV logic
    # Note: original code expected plural sets (parents, tickers, etc).
    # We simplified to singular best-match. We must return dict compatible with main loop usage.
    # Main loop usage: 
    # ticker: "; ".join(sorted(enrichment["tickers"]))
    # exchange: ... enrichment["exchanges"]
    
    return {
        "parents": {res.get("currentName", {}).get("value")},
        "subsidiaries": set(),
        "tickers": {ticker} if ticker != "PRIVATE" else set(),
        "exchanges": {res.get("exchangeLabel", {}).get("value")} if "exchangeLabel" in res else set(),
        "countries": set(),
        "sec_cik": None,
        "dissolved": "dissolved" in res
    }

def clean_company_name(name: str) -> str:
    """
    Remove common corporate suffixes to improve matching chances.
    """
    import re
    # Common suffixes to remove (case insensitive)
    suffixes = [
        r",?\s+Inc\.?$", r",?\s+Incorporated$", 
        r",?\s+LLC$", r",?\s+L\.L\.C\.$", 
        r",?\s+LP$", r",?\s+L\.P\.$", 
        r",?\s+Ltd\.?$", r",?\s+Limited$", 
        r",?\s+Corp\.?$", r",?\s+Corporation$", 
        r",?\s+PLC$", r",?\s+S\.A\.$", 
        r",?\s+GmbH$", r",?\s+N\.V\.$",
        r",?\s+B\.V\.$"
    ]
    
    cleaned = name
    for pattern in suffixes:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()

def search_wikidata_candidates(name, limit=5):
    """
    Returns list of top QIDs matching the name.
    """
    api_url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": limit,
        "type": "item"
    }
    headers = {
        'User-Agent': 'BioTechBot/1.0 (https://example.com/) PythonRequests/2.31'
    }
    
    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [r["id"] for r in data.get("search", [])]
    except Exception as e:
        print(f"Search API error for '{name}': {e}")
        return []

def validate_company_candidates(qids):
    """
    Given a list of QIDs, return the best one that appears to be a company/organization.
    Scores candidates based on data richness (Ticker > Parent > Owner).
    Also recognizes historical/merged companies via P1366 (replaced by) and P576 (dissolved).
    """
    if not qids:
         return None
         
    # Construct VALUES clause
    values_str = " ".join([f"wd:{q}" for q in qids])
    
    # Query to check attributes - include historical company markers
    query = f"""
    SELECT DISTINCT ?item ?hasTicker ?hasParent ?hasOwner ?isCompany ?wasReplaced ?wasDissolved WHERE {{
      VALUES ?item {{ {values_str} }}
      
      OPTIONAL {{ ?item wdt:P249 ?ticker. BIND(1 AS ?hasTicker) }}
      OPTIONAL {{ ?item wdt:P749 ?parent. BIND(1 AS ?hasParent) }}
      OPTIONAL {{ ?item wdt:P127 ?owner. BIND(1 AS ?hasOwner) }}
      OPTIONAL {{ ?item wdt:P1366 ?successor. BIND(1 AS ?wasReplaced) }}
      OPTIONAL {{ ?item wdt:P576 ?dissolved. BIND(1 AS ?wasDissolved) }}
      
      # Check instance type
      {{
        ?item wdt:P31/wdt:P279* wd:Q43229 . BIND(1 AS ?isCompany)
      }} UNION {{
        ?item wdt:P31/wdt:P279* wd:Q4830453 . BIND(1 AS ?isCompany)
      }}
    }}
    """
    
    try:
        rows = _run_sparql_query(query, "Validation")
    except Exception:
        return None
        
    if not rows:
        return None
        
    scores = {}
    for r in rows:
        qid = r['item']['value'].split('/')[-1]
        score = 0
        if r.get('isCompany'): score += 1
        if r.get('hasOwner'): score += 2
        if r.get('hasParent'): score += 3
        if r.get('wasReplaced'): score += 4  # Historical company - good signal!
        if r.get('wasDissolved'): score += 2  # Another historical marker
        if r.get('hasTicker'): score += 5
        
        # Skip if not a company at all
        if score == 0:
             continue
             
        scores[qid] = score

    # Pick the highest scoring candidate
    best_candidate = None
    best_score = -1
    
    for q in qids:
        if q in scores:
            if scores[q] > best_score:
                best_score = scores[q]
                best_candidate = q
                
    return best_candidate

def search_wikidata_id(name):
    """
    Wrapper to perform Smart Search: Get candidates -> Filter for Company.
    Tries multiple name variations to maximize match chances.
    """
    import re
    
    # Create search variations
    variations = [name]
    
    # Strip common pharma suffixes to get base name
    suffixes_to_strip = [
        r"\s+Pharmaceuticals?$", r"\s+Biotech$", r"\s+Therapeutics$",
        r"\s+Biosciences$", r"\s+Company$", r"\s+Sciences$",
        r",?\s+Inc\.?$", r",?\s+LLC$", r",?\s+LP$", r",?\s+Ltd\.?$"
    ]
    stripped = name
    for pattern in suffixes_to_strip:
        stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE).strip()
    if stripped != name and stripped:
        variations.append(stripped)
    
    # Try first word for multi-word names (e.g., "GEIGY Pharmaceuticals" -> "GEIGY")
    words = name.split()
    if len(words) > 1:
        first_word = words[0]
        if first_word not in variations and len(first_word) > 3:
            variations.append(first_word)
    
    # Add pharma/biotech suffixes for short names
    if " " not in name or len(name) < 15:
        suffixes = [" Pharmaceuticals", " Pharmaceutica", " Biotech", " Therapeutics"]
        for suffix in suffixes:
            if suffix.lower() not in name.lower():
                variations.append(name + suffix)
    
    all_candidates = []
    seen = set()
    
    for search_term in variations:
        candidates = search_wikidata_candidates(search_term)
        for q in candidates:
            if q not in seen:
                all_candidates.append(q)
                seen.add(q)
                
    if all_candidates:
        return validate_company_candidates(all_candidates)
                
    return None

def find_company_by_name(name: str):
    """
    Stage 1.5: Fallback Identity Query using API Search.
    """
    # 1. Try search with cleaning (advanced fallback handled inside search_wikidata_id)
    # Removing just the INC/LLC suffixes before search might help, or we rely on the API.
    # We kept clean_company_name function? We can use it.
    
    qid = search_wikidata_id(name)
    if not qid:
        clean = clean_company_name(name)
        if clean != name:
             qid = search_wikidata_id(clean)
             
    if qid:
        return f"http://www.wikidata.org/entity/{qid}"
    return None

def load_industry_sponsors(filepath: str):
    """
    Reads the pipe-delimited sponsors file and returns a list of dicts 
    {'nct_id': str, 'name': str} where the agency_class is 'INDUSTRY'.
    """
    sponsors = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='|')
            for row in reader:
                if row.get('agency_class') == 'INDUSTRY':
                    nct = row.get('nct_id')
                    name = row.get('name')
                    if nct and name:
                        sponsors.append({'nct_id': nct, 'name': name})
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Sort by NCT ID
    sponsors.sort(key=lambda x: x['nct_id'])
    return sponsors

def main():
    parser = argparse.ArgumentParser(description="Resolve industry sponsors from clinical trials via Wikidata.")
    parser.add_argument("--sponsors-file", default="data/sponsors.txt", help="Path to the AAAT sponsors.txt file")
    parser.add_argument("--limit", type=int, help="Limit the number of NCT IDs to process")
    parser.add_argument("--output", default="sponsors_resolved.csv", help="Output CSV filename")
    
    args = parser.parse_args()

    print(f"Loading industry sponsors from {args.sponsors_file}...")
    sponsor_records = load_industry_sponsors(args.sponsors_file)
    print(f"Found {len(sponsor_records)} unique industry-sponsored trials.")

    if args.limit:
        print(f"Limiting to first {args.limit} IDs.")
        sponsor_records = sponsor_records[:args.limit]

    print(f"Processing {len(sponsor_records)} trials...")

    # Output fieldnames
    fieldnames = ["nct_id", "company", "ticker", "exchange", "status", "wikidata_uri"]

    with open(args.output, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for i, record in enumerate(sponsor_records):
            nct_id = record['nct_id']
            sponsor_name = record['name']
            
            print(f"[{i+1}/{len(sponsor_records)}] Resolving {nct_id} ({sponsor_name})...", end="", flush=True)
            
            company_uri = None
            company_label = sponsor_name

            # Stage 1: Try Identity via NCT Link
            identity = get_trial_primary_sponsor(nct_id)
            if identity["company_uri"]:
                company_uri = identity["company_uri"]
                company_label = identity["company_label"] # Prefer Wikidata label if linked
            else:
                # Stage 1.5: Fallback to Name Search
                # print(" (Linking via name)...", end="", flush=True)
                company_uri = find_company_by_name(sponsor_name)
            
            if company_uri:
                print(f" [URI: {company_uri.split('/')[-1]}]", end="")
            
            if not company_uri:
                print(" No match.")
                writer.writerow({
                    "nct_id": nct_id,
                    "company": sponsor_name,
                    "ticker": "N/A", 
                    "exchange": "N/A", 
                    "status": "N/A",
                    "wikidata_uri": ""
                })
                continue

            # Stage 2: Enrichment
            enrichment = enrich_company_content(company_uri, company_label)
            
            status = "Active"
            if enrichment.get("dissolved"): status = "Inactive"

            row = {
                "nct_id": nct_id,
                "company": company_label,
                "ticker": "; ".join(sorted(enrichment["tickers"])) if enrichment["tickers"] else "Private/Unlisted",
                "exchange": "; ".join(sorted(enrichment["exchanges"])) if enrichment["exchanges"] else "N/A",
                "status": status,
                "wikidata_uri": company_uri
            }
            writer.writerow(row)
            print(" Done.")

    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
