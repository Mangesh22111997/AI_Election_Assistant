import os
import asyncio
from dotenv import load_dotenv
from backend.agents.guide_agent import GuideAgent
from backend.agents.simplifier_agent import SimplifierAgent
from backend.agents.safety_monitor import SafetyMonitor

async def main():
    load_dotenv()
    print("🚀 Initialising agents...")
    
    guide = GuideAgent()
    simplifier = SimplifierAgent()
    monitor = SafetyMonitor()
    
    queries = [
        "How do I register to vote in India?",
        "What are the ID requirements for voting?",
        "When is the next election?"
    ]
    
    for query in queries:
        print(f"\n\n{'='*50}")
        print(f"❓ Query: {query}")
        print(f"{'='*50}")
        
        # 1. Input Safety
        print("\n🛡️  Step 1: Input Safety Check...")
        input_safety = monitor.validate_input(query)
        if not input_safety.passed:
            print(f"❌ BLOCKED: {input_safety.violation_type}")
            continue
        print("✅ PASSED")
        
        # 2. Guide Agent (RAG)
        print("\n📚 Step 2: Guide Agent (Retrieval + Generation)...")
        try:
            guide_result = guide.process_query(query)
            raw_answer = guide_result["answer"]
            intent = guide_result["intent"]
            sources = guide_result["sources"]
            print(f"🎯 Intent: {intent}")
            print(f"📖 Sources: {sources}")
            print(f"📝 Raw Answer: {raw_answer[:200]}...")
        except Exception as e:
            print(f"🔥 Guide Agent failed: {e}")
            continue
            
        # 3. Simplifier Agent
        print("\n✨ Step 3: Simplifier Agent (Readability)...")
        try:
            simplified, grade = simplifier.simplify(raw_answer)
            print(f"📊 Reading Grade: {grade}")
            print(f"💡 Simplified: {simplified[:200]}...")
        except Exception as e:
            print(f"🔥 Simplifier failed: {e}")
            continue
            
        # 4. Output Safety
        print("\n🛡️  Step 4: Output Safety Audit...")
        output_safety = monitor.validate(simplified, query)
        if not output_safety.passed:
            print(f"❌ BLOCKED: {output_safety.violation_type}")
        else:
            print("✅ PASSED")
            print("\n🌟 FINAL OUTPUT:")
            print(output_safety.output)

if __name__ == "__main__":
    asyncio.run(main())
