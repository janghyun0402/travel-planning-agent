"""에이전트 오케스트레이션.

ChatAgent: 독립 멀티턴 대화 (API 레이어에서 직접 사용)
PipelineAgent: trip_request 확정 후 백그라운드 실행
  Crawl → Merge → Reserve → Itinerary → Response
"""

from google.adk.agents import SequentialAgent

from agents.crawler_agent import crawler_agent
from agents.merger_agent import merger_agent
from agents.reserver_agent import reserver_agent
from agents.itinerary_agent import itinerary_agent
from agents.response_agent import response_agent

pipeline_agent = SequentialAgent(
    name="TravelPipelineAgent",
    sub_agents=[crawler_agent, merger_agent, reserver_agent, itinerary_agent, response_agent],
    description="Executes the travel planning pipeline: crawl → merge → reserve → itinerary → response.",
)
