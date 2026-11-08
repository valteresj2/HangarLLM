"""
New Relic AI Monitoring Integration for HangarLLM

This module provides integration with New Relic's AI Monitoring feature to track
LLM requests, responses, and usage metrics.
"""

from hangarllm.integrations.newrelic.newrelic import NewRelicLogger

__all__ = ["NewRelicLogger"]
