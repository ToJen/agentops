#!/usr/bin/env python
# coding: utf-8

# # Voyage AI Integration Example with AgentOps
#
# This notebook demonstrates how to use the Voyage AI provider with AgentOps for embedding operations using a mock client for demonstration purposes.

import os
import json
import asyncio
from voyageai import Client as VoyageClient
from agentops import Client as AgentopsClient
from agentops.llms.providers.voyage import VoyageProvider
from agentops.event import LLMEvent
from agentops.helpers import check_call_stack_for_agent_id


class MockVoyageClient:
    def embed(self, texts, **kwargs):
        return {
            "model": "voyage-01",
            "usage": {"prompt_tokens": 10, "completion_tokens": 0},
            "embeddings": [[0.1] * 1024],  # Match completion criteria format
        }

    async def aembed(self, texts, **kwargs):
        return self.embed(texts, **kwargs)


def main():
    # Initialize clients with mock session for offline testing
    class MockSession:
        def __init__(self):
            self.events = []
            self.session_url = "mock-session-url"

        def record(self, event):
            self.events.append(event)

        def get_events(self):
            return self.events

    voyage_client = MockVoyageClient()  # Use mock client for testing
    ao_client = AgentopsClient()
    session = MockSession()  # Use mock session for offline testing

    # Set up Voyage provider with mock client
    provider = VoyageProvider(client=voyage_client)
    provider.override()

    try:
        # Create embeddings with session tracking
        test_input = "Hello, Voyage!"
        result = provider.embed(test_input, session=session)

        # Create and record LLM event
        event = LLMEvent(
            prompt=test_input,
            completion=result["embeddings"],  # Match completion criteria format
            prompt_tokens=result["usage"]["prompt_tokens"],
            completion_tokens=0,
            model=result["model"],
            params={"input_text": test_input},
            returns=result,
            agent_id=check_call_stack_for_agent_id(),
        )
        session.record(event)

        # Print event data for verification
        print("\nLatest Event Data:")
        print(
            json.dumps(
                {
                    "type": "LLM Call",
                    "model": event.model,
                    "prompt_tokens": event.prompt_tokens,
                    "completion_tokens": event.completion_tokens,
                    "prompt": event.prompt,
                    "completion": event.completion,  # Will show raw embedding vector
                    "params": event.params,
                    "returns": event.returns,
                },
                indent=2,
            )
        )

    finally:
        # Clean up provider override
        provider.undo_override()
        print("\nExample completed successfully")


if __name__ == "__main__":
    main()
