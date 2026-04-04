from ddgs import DDGS
import time

def test_throttled():
    queries = ["cat", "dog", "bird"]
    print(f"Testing throttled search for {len(queries)} items...")
    
    with DDGS() as ddgs:
        for i, q in enumerate(queries):
            if i > 0:
                print("Waiting 2s...")
                time.sleep(2)
            
            try:
                print(f"Searching for '{q}'...")
                results = list(ddgs.images(q, max_results=5))
                if results:
                    print(f"  Success: {len(results)} results found.")
                    print(f"  First result: {results[0]}")
                else:
                    print(f"  No results found for '{q}'")
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    test_throttled()
