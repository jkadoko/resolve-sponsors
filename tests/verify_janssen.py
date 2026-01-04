from resolve_sponsor_v2 import resolve_wikidata_entity
import json

def test_janssen():
    print("Testing 'Janssen' resolution...")
    # Passing dummy NCT ID as we rely on name search
    result = resolve_wikidata_entity("Janssen", "NCT00000000")
    print(json.dumps(result, indent=2))

    print("\nTesting 'Janssen, LP' resolution...")
    result_lp = resolve_wikidata_entity("Janssen, LP", "NCT00000000")
    print(json.dumps(result_lp, indent=2))

if __name__ == "__main__":
    test_janssen()
