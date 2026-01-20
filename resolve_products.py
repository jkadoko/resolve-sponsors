import argparse
import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Use standard Wikidata SPARQL endpoint
QLEVER_ENDPOINT = "https://query.wikidata.org/sparql"
# Standard User-Agent for Wikidata policy
HEADERS = {"User-Agent": "BiotechAnalyzer/1.0 ([EMAIL_ADDRESS])"}

def _get_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.0, # 1s, 2s, 4s, 8s, 16s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

SESSION = _get_session()

def _run_sparql_query(query: str, purpose: str):
    """
    Helper to run SPARQL query with retries and timeout.
    """
    timeout = 60
    
    try:
        response = SESSION.get(
            QLEVER_ENDPOINT,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        bindings = data["results"]["bindings"]
        if not bindings:
             print(f"DEBUG: SPARQL query returned 0 bindings.", file=sys.stderr)
             # print(f"DEBUG: Raw response: {data}", file=sys.stderr) 
        return bindings
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f"\nResponse: {e.response.text}"
        print(f"Error querying ({purpose}): {error_msg}", file=sys.stderr)
        return None

def get_company_by_ticker(ticker: str):
    """
    Finds the company URI and label associated with the Ticker Symbol (P249).
    """
    # Use FILTER for ticker to be safer against string types
    query = f"""
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?company ?companyLabel WHERE {{
        ?company wdt:P249 ?ticker .
        FILTER(STR(?ticker) = "{ticker}")
        
        OPTIONAL {{ 
            ?company rdfs:label ?companyLabel .
            FILTER (lang(?companyLabel) = "en") 
        }}
    }}
    LIMIT 1
    """
    
    print(f"DEBUG: Running query for ticker {ticker}...")
    rows = _run_sparql_query(query, f"Ticker-{ticker}")
    
    if rows:
        row = rows[0]
        uri = row.get("company", {}).get("value")
        label = row.get("companyLabel", {}).get("value", "Unknown")
        print(f"DEBUG: Found {label} ({uri})")
        return {
            "company_uri": uri,
            "company_label": label
        }

    print(f"DEBUG: Direct SPARQL failed. Trying fallback search for '{ticker}'...")
    
    # Fallback: Search using MediaWiki API (wbsearchentities)
    # This finds items where 'ticker' is a label or alias
    api_url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": ticker,
        "language": "en",
        "format": "json",
        "limit": 5,
        "type": "item"
    }
    
    try:
        resp = SESSION.get(api_url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        search_results = resp.json().get("search", [])
    except Exception as e:
        print(f"DEBUG: Search API failed: {e}", file=sys.stderr)
        return None

    if not search_results:
        print(f"DEBUG: No search results for '{ticker}'")
        return None
        
    candidate_map = {r["id"]: r.get("label", "Unknown") for r in search_results}
    candidate_qids = list(candidate_map.keys())
    values_str = " ".join([f"wd:{q}" for q in candidate_qids])
    
    # Relaxed verify query: Get candidates and ANY P249 they might have
    # Also check p:P414 (Exchange) -> pq:P249 (Ticker)
    verify_query = f"""
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX p: <http://www.wikidata.org/prop/>
    PREFIX ps: <http://www.wikidata.org/prop/statement/>
    PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
    
    SELECT ?item ?ticker ?ticker2 ?ticker3 WHERE {{
        VALUES ?item {{ {values_str} }}
        OPTIONAL {{ ?item wdt:P249 ?ticker . }}
        OPTIONAL {{ ?item p:P249/ps:P249 ?ticker2 . }}
        OPTIONAL {{ 
            ?item p:P414 ?exchangeStmt .
            ?exchangeStmt pq:P249 ?ticker3 .
        }}
    }}
    """
    
    verify_query = f"""
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX p: <http://www.wikidata.org/prop/>
    PREFIX ps: <http://www.wikidata.org/prop/statement/>
    PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
    
    SELECT ?item ?ticker ?ticker2 ?ticker3 ?companyRef ?companyRefLabel ?operatorRef ?operatorRefLabel WHERE {{
        VALUES ?item {{ {values_str} }}
        OPTIONAL {{ ?item wdt:P249 ?ticker . }}
        OPTIONAL {{ ?item p:P249/ps:P249 ?ticker2 . }}
        OPTIONAL {{ 
            ?item p:P414 ?exchangeStmt .
            ?exchangeStmt pq:P249 ?ticker3 .
        }}
        # Check if item itself IS the stock (ADR/listing) and points to company
        OPTIONAL {{ ?item wdt:P361 ?companyRef . ?companyRef rdfs:label ?companyRefLabel . FILTER(LANG(?companyRefLabel)="en") }}
        OPTIONAL {{ ?item wdt:P137 ?operatorRef . ?operatorRef rdfs:label ?operatorRefLabel . FILTER(LANG(?operatorRefLabel)="en") }}
        OPTIONAL {{ ?item skos:altLabel ?alias . FILTER(LANG(?alias)="en") }}
    }}
    """
    
    verify_rows = _run_sparql_query(verify_query, f"Verify-{ticker}")
    
    if verify_rows:
        for r in verify_rows:
            t1 = r.get("ticker", {}).get("value")
            t2 = r.get("ticker2", {}).get("value")
            t3 = r.get("ticker3", {}).get("value")
            
            # Pick first non-null
            found_ticker = t1 or t2 or t3
            
            uri = r.get("item", {}).get("value")
            qid = uri.split("/")[-1]
            label = candidate_map.get(qid, "Unknown")
            alias = r.get("alias", {}).get("value")
            
            # Case 1: The item found HAS the ticker property
            if found_ticker and found_ticker.strip().upper() == ticker.strip().upper():
                print(f"DEBUG: Match found! {label} ({uri})")
                return {
                    "company_uri": uri,
                    "company_label": label
                }
            
            # Case 2: The item IS the ticker/stock (e.g. "NVO" item) and points to company
            if (label.strip().upper() == ticker.strip().upper() or "ADR" in label):
                 company_uri = r.get("companyRef", {}).get("value") or r.get("operatorRef", {}).get("value")
                 company_lbl = r.get("companyRefLabel", {}).get("value") or r.get("operatorRefLabel", {}).get("value")
                 
                 if company_uri:
                      print(f"DEBUG: Ticker/ADR item found: {label} -> Linked Company: {company_lbl} ({company_uri})")
                      return {
                         "company_uri": company_uri,
                         "company_label": company_lbl
                      }
            
            # Case 3: The item found HAS the ticker as an alias (and is a business)
            if alias and alias.strip().upper() == ticker.strip().upper():
                 # Confirm it is likely a company (has products or is subclass of business)
                 print(f"DEBUG: Alias match found! {label} ({uri}) matches '{alias}'")
                 return {
                    "company_uri": uri,
                    "company_label": label
                 }
    
    print(f"DEBUG: Fallback candidates {candidate_qids} did not match ticker '{ticker}'")
    return None

def get_products_for_company(company_uri: str):
    """
    Finds commercial products (P1056) associated with the company.
    """
    company_qid = company_uri.split("/")[-1]
    
    query = f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?product ?productLabel WHERE {{
        {{
            wd:{company_qid} wdt:P1056 ?product .
        }} UNION {{
            ?product wdt:P176 wd:{company_qid} .
        }}
        ?product rdfs:label ?productLabel .
        FILTER (lang(?productLabel) = "en")
        
        # Filter out generic terms
        FILTER (?productLabel != "medication"@en)
        FILTER (?productLabel != "pharmaceutical product"@en)
        FILTER (?productLabel != "drug"@en)
    }}
    LIMIT 50
    """
    
    rows = _run_sparql_query(query, f"Products-{company_qid}") or []
    
    products = []
    for row in rows:
        products.append({
            "product_uri": row.get("product", {}).get("value"),
            "product_label": row.get("productLabel", {}).get("value")
        })
    return products

def main():
    parser = argparse.ArgumentParser(description="Resolve commercial products for a company ticker via Wikidata.")
    parser.add_argument("ticker", help="The stock ticker symbol (e.g., PFE, MRK)")
    
    args = parser.parse_args()
    
    print(f"Resolving company for ticker: {args.ticker}...")
    company = get_company_by_ticker(args.ticker)
    
    if not company:
        print(f"No company found for ticker '{args.ticker}'.")
        sys.exit(1)
        
    print(f"Found Company: {company['company_label']} ({company['company_uri']})")
    
    print("Fetching products...")
    products = get_products_for_company(company['company_uri'])
    
    if not products:
        print("No products found listed in Wikidata.")
    else:
        print(f"Found {len(products)} products:")
        for p in products:
            print(f"- {p['product_label']}")

if __name__ == "__main__":
    main()
