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
    
    query = "How do I register to vote in India?"
    print(f"\n❓ Query: {query}")
    
    # 1. Input Safety
    print("\n🛡️  Step 1: Input Safety Check...")
    input_safety = monitor.validate_input(query)
    print(f"✅ PASSED: {input_safety.passed}")
    
    # 2. Guide Agent
    print("\n📚 Step 2: Guide Agent...")
    guide_result = guide.process_query(query)
    print(f"🎯 Intent: {guide_result['intent']}")
    print(f"📝 Raw Answer: {guide_result['answer'][:500]}")
    
    # Wait to avoid quota
    print("\n⏳ Sleeping 15s to respect quota...")
    await asyncio.sleep(15)
    
    # 3. Simplifier Agent
    print("\n✨ Step 3: Simplifier Agent...")
    simplified, grade = simplifier.simplify(guide_result['answer'])
    print(f"📊 Reading Grade: {grade}")
    print(f"💡 Simplified: {simplified[:500]}")

if __name__ == "__main__":
    asyncio.run(main())
