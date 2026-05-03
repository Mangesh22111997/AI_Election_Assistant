import os
from dotenv import load_dotenv
from backend.services.grounding_tool import GroundingTool

def main():
    load_dotenv()
    gt = GroundingTool()
    
    query = "How do I register to vote in India?"
    print(f"🔍 Debugging RAG for: {query}")
    
    results = gt.retrieve(query, n_results=5, similarity_threshold=0.3)
    
    print(f"\nFound {len(results)} results:")
    for i, res in enumerate(results, 1):
        print(f"\n--- Result {i} (Source: {res['source']}, Score: {res['score']}) ---")
        print(res['content'][:500])

if __name__ == "__main__":
    main()
