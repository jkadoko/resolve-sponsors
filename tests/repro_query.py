import requests
import sys

QLEVER_ENDPOINT = "https://query.wikidata.org/sparql"

def test_query(nct_id):
    print(f"Testing {nct_id}...")
    query = f"""
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    SELECT ?trial ?trialLabel WHERE {{
        ?trial wdt:P3098 "{nct_id}" .
        optional {{ ?trial rdfs:label ?trialLabel filter (lang(?trialLabel) = "en") }}
    }}
    """
    
    headers = {
        "User-Agent": "BiotechAnalyzer/1.0 (contact@example.com)"
    }
    
    try:
        response = requests.get(
            QLEVER_ENDPOINT,
            params={"query": query, "format": "json"},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        bindings = data["results"]["bindings"]
        print(f"Found {len(bindings)} results.")
        for b in bindings:
            print(f"  Trial: {b.get('trialLabel', {}).get('value')}")
            print(f"  Company: {b.get('companyLabel', {}).get('value')}")
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")

if __name__ == "__main__":
    test_query("NCT04470427") # Known good from original script
    test_query("NCT00000174") # One from the file
