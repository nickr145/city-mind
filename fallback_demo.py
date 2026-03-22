# fallback_demo.py — run directly from project root if LangGraph Studio is unavailable
# Usage: python fallback_demo.py
from dotenv import load_dotenv

load_dotenv()

from agent.agent import graph

queries = [
    "What is the water infrastructure readiness for the Uptown Waterloo corridor? I am a city planner reviewing development permit applications.",
    "What are the environmental and infrastructure risk factors in zone WR-ZONE-042? I am a public health official investigating a potential disease cluster.",
    "Which zones have both high development pressure from permits and high infrastructure strain? Give me a cross-department overview. I am an analyst.",
]

for q in queries:
    print(f"\n{'=' * 60}\nQ: {q}\n{'=' * 60}")
    result = graph.invoke({"messages": [{"role": "user", "content": q}]})
    print(result["messages"][-1].content)
