import ijson
import csv
import sys
import os
from collections import defaultdict

# Import resolution logic from existing script
# Ensure current directory is in path to find resolve_sponsor module
sys.path.append(os.getcwd())
try:
    from resolve_sponsor import find_company_by_name, enrich_company_content
except ImportError:
    print("Error: Could not import resolve_sponsor.py. Make sure you are running this from the correct directory.")
    sys.exit(1)

INPUT_FILE = r"data/drug-drugsfda-0001-of-0001.json"
OUTPUT_FILE = "products.csv"

def load_and_group_products(filepath):
    """
    Reads OpenFDA JSON stream and groups products by sponsor.
    Returns: dict { "Sponsor Name": [List of Product Dicts] }
    """
    print(f"Reading OpenFDA data from {filepath}...")
    sponsor_map = defaultdict(list)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Stream 'results.item' - each item is an application record
            objects = ijson.items(f, 'results.item')
            
            count = 0
            for record in objects:
                count += 1
                if count % 1000 == 0:
                    print(f"Processed {count} records...", end='\r')
                    
                sponsor = record.get("sponsor_name", "UNKNOWN")
                products = record.get("products", [])
                openfda = record.get("openfda", {})
                
                # Sometimes openfda block has better brand names
                fda_brand_names = openfda.get("brand_name", [])
                
                # Extract RxCUI from openfda block (list of strings)
                rxcui_list = openfda.get("rxcui", [])
                rxcui_str = "; ".join(rxcui_list) if rxcui_list else ""
                
                for i, prod in enumerate(products):
                    # Flatten product info
                    brand_name = prod.get("brand_name", "Unknown")
                    
                    # If brand name is missing or generic, try to use openfda enrichment
                    if (not brand_name or brand_name == "Unknown") and i < len(fda_brand_names):
                        brand_name = fda_brand_names[i]
                    
                    # Separate Active Ingredients Name and Strength
                    ingredients = prod.get("active_ingredients", [])
                    ai_names = "; ".join([ai.get("name", "") for ai in ingredients])
                    ai_strengths = "; ".join([ai.get("strength", "") for ai in ingredients])
                    
                    product_data = {
                        "product_name": brand_name,
                        "active_ingredients_name": ai_names,
                        "active_ingredients_strength": ai_strengths,
                        "rxcui": rxcui_str,
                        "marketing_status": prod.get("marketing_status", "Unknown"),
                        "dosage_form": prod.get("dosage_form", "Unknown")
                    }
                    sponsor_map[sponsor].append(product_data)
                    
            print(f"\nFinished reading {count} records.")
            return sponsor_map
            
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        sys.exit(1)

import argparse

def main():
    parser = argparse.ArgumentParser(description="Extract and resolve products from OpenFDA.")
    parser.add_argument("--limit", type=int, help="Limit number of sponsors to resolve")
    parser.add_argument("--filter", type=str, help="Filter for sponsors containing this string (case-insensitive)")
    args = parser.parse_args()

    # 1. Load Data
    print("--- Step 1: Extracting Products ---")
    sponsor_product_map = load_and_group_products(INPUT_FILE)
    
    unique_sponsors = list(sponsor_product_map.keys())
    print(f"Found {len(unique_sponsors)} unique sponsors.")
    
    # Filter sponsors if requested
    if args.filter:
        print(f"Filtering for sponsors containing '{args.filter}'...")
        unique_sponsors = [s for s in unique_sponsors if args.filter.lower() in s.lower()]
        print(f"Found {len(unique_sponsors)} matching sponsors.")
    
    # Limit if requested
    if args.limit:
        print(f"Limiting to first {args.limit} sponsors.")
        unique_sponsors = unique_sponsors[:args.limit]
    
    # 2. Resolve Sponsors
    print("\n--- Step 2: Resolving Sponsors ---")
    
    # Define CSV Headers
    fieldnames = [
        "product_name", "active_ingredients_name", "active_ingredients_strength", 
        "rxcui", "marketing_status", "dosage_form",
        "openfda_sponsor_name", "resolved_sponsor_name", 
        "ticker", "exchange", "status", "wikidata_uri"
    ]
    
    resolved_cache = {}
    unresolved_sponsors = []
    
    # Output file name adjusts if filter used
    output_filename = OUTPUT_FILE
    if args.filter:
        output_filename = f"products_{args.filter.lower().replace(' ', '_')}.csv"
    
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, sponsor in enumerate(unique_sponsors):
            # Progress update
            print(f"Resolving sponsor {i+1}/{len(unique_sponsors)}: {sponsor}...", end='\r')
            
            # Resolve Sponsor (or get from cache)
            if sponsor in resolved_cache:
                resolution = resolved_cache[sponsor]
            else:
                # 1. Find URI
                uri = find_company_by_name(sponsor) # Imports from resolve_sponsor
                
                if uri:
                    # 2. Enrich
                    enrichment = enrich_company_content(uri, sponsor)
                    
                    # Format
                    ticker_str = "; ".join(sorted(enrichment["tickers"])) if enrichment["tickers"] else "Private/Unlisted"
                    exchange_str = "; ".join(sorted(enrichment["exchanges"])) if enrichment["exchanges"] else "N/A"
                    status_str = "Inactive" if enrichment.get("dissolved") else "Active"
                    parent_name = list(enrichment["parents"])[0] if enrichment["parents"] else sponsor
                    
                    resolution = {
                        "name": parent_name, # Use Parent/Current Name
                        "ticker": ticker_str,
                        "exchange": exchange_str,
                        "status": status_str,
                        "uri": uri
                    }
                else:
                    resolution = {
                        "name": sponsor,
                        "ticker": "N/A",
                        "exchange": "N/A",
                        "status": "Unresolved",
                        "uri": ""
                    }
                    unresolved_sponsors.append(sponsor)
                
                resolved_cache[sponsor] = resolution
            
            # Write all products for this sponsor
            products = sponsor_product_map[sponsor]
            for prod in products:
                row = {
                    "product_name": prod["product_name"],
                    "active_ingredients_name": prod["active_ingredients_name"],
                    "active_ingredients_strength": prod["active_ingredients_strength"],
                    "rxcui": prod["rxcui"],
                    "marketing_status": prod["marketing_status"],
                    "dosage_form": prod["dosage_form"],
                    "openfda_sponsor_name": sponsor,
                    "resolved_sponsor_name": resolution["name"],
                    "ticker": resolution["ticker"],
                    "exchange": resolution["exchange"],
                    "status": resolution["status"],
                    "wikidata_uri": resolution["uri"]
                }
                writer.writerow(row)
    
    # Write Unresolved Sponsors List
    with open("unresolved_sponsors.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["unresolved_sponsor_name"])
        for s in unresolved_sponsors:
            writer.writerow([s])

    print(f"\nDone! Products saved to {OUTPUT_FILE}")
    print(f"Unresolved sponsors saved to 'unresolved_sponsors.csv' ({len(unresolved_sponsors)} entries).")

if __name__ == "__main__":
    main()
