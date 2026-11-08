### What this tests ####
## This test asserts the type of data passed into each method of the custom callback handler
import asyncio
import inspect
import json
import time
import traceback
from hangarllm._uuid import uuid
from datetime import datetime

import pytest
from pydantic import BaseModel

from typing import List, Literal, Optional, Union
from unittest.mock import AsyncMock, MagicMock, patch

import hangarllm
from hangarllm import Cache, completion, embedding
from hangarllm.integrations.custom_logger import CustomLogger
from hangarllm.types.utils import HangarLLMCommonStrings

# Test Scenarios (test across completion, streaming, embedding)
## 1: Pre-API-Call
## 2: Post-API-Call
## 3: On HangarLLM Call success
## 4: On HangarLLM Call failure
## 5. Caching

# Test models
## 1. OpenAI
## 2. Azure OpenAI
## 3. Non-OpenAI/Azure - e.g. Bedrock

# Test interfaces
## 1. hangarllm.completion() + hangarllm.embeddings()
## refer to test_custom_callback_input_router.py for the router +  proxy tests


class CompletionCustomHandler(
    CustomLogger
):  # https://github.com/valteresj2/HangarLLM#readme
    """
    The set of expected inputs to a custom handler for a
    """

    # Class variables or attributes
    def __init__(self):
        self.errors = []
        self.states: List[
            Literal[
                "sync_pre_api_call",
                "async_pre_api_call",
                "post_api_call",
                "sync_stream",
                "async_stream",
                "sync_success",
                "async_success",
                "sync_failure",
                "async_failure",
            ]
        ] = []

    def log_pre_api_call(self, model, messages, kwargs):
        try:
            self.states.append("sync_pre_api_call")
            ## MODEL
            assert isinstance(model, str)
            ## MESSAGES
            assert isinstance(messages, list)
            ## KWARGS
            assert isinstance(kwargs["model"], str)
            assert isinstance(kwargs["messages"], list)
            assert isinstance(kwargs["optional_params"], dict)
            assert isinstance(kwargs["hangarllm_params"], dict)
            assert isinstance(kwargs["start_time"], (datetime, type(None)))
            assert isinstance(kwargs["stream"], bool)
            assert isinstance(kwargs["user"], (str, type(None)))
            ### METADATA
            metadata_value = kwargs["hangarllm_params"].get("metadata")
            assert metadata_value is None or isinstance(metadata_value, dict)
            if metadata_value is not None:
                if hangarllm.turn_off_message_logging is True:
                    assert (
                        metadata_value["raw_request"]
                        is HangarLLMCommonStrings.redacted_by_hangarllm.value
                    )
                else:
                    assert "raw_request" not in metadata_value or isinstance(
                        metadata_value["raw_request"], str
                    )
        except Exception:
            print(f"Assertion Error: {traceback.format_exc()}")
            self.errors.append(traceback.format_exc())

    def log_post_api_call(self, kwargs, response_obj, start_time, end_time):
        try:
            self.states.append("post_api_call")
            ## START TIME
            assert isinstance(start_time, datetime)
            ## END TIME
            assert end_time == None
            ## RESPONSE OBJECT
            assert response_obj == None
            ## KWARGS
            assert isinstance(kwargs["model"], str)
            assert isinstance(kwargs["messages"], list)
            assert isinstance(kwargs["optional_params"], dict)
            assert isinstance(kwargs["hangarllm_params"], dict)
            assert isinstance(kwargs["start_time"], (datetime, type(None)))
            assert isinstance(kwargs["stream"], bool)
            assert isinstance(kwargs["user"], (str, type(None)))
            assert isinstance(kwargs["input"], (list, dict, str))
            assert isinstance(kwargs["api_key"], (str, type(None)))
            assert (
                isinstance(
                    kwargs["original_response"],
                    (str, hangarllm.CustomStreamWrapper, BaseModel),
                )
                or inspect.iscoroutine(kwargs["original_response"])
                or inspect.isasyncgen(kwargs["original_response"])
            )
            assert isinstance(kwargs["additional_args"], (dict, type(None)))
            assert isinstance(kwargs["log_event_type"], str)
        except Exception:
            print(f"Assertion Error: {traceback.format_exc()}")
            self.errors.append(traceback.format_exc())

    async def async_log_stream_event(self, kwargs, response_obj, start_time, end_time):
        try:
            self.states.append("async_stream")
            ## START TIME
            assert isinstance(start_time, datetime)
            ## END TIME
            assert isinstance(end_time, datetime)
            ## RESPONSE OBJECT
            assert isinstance(response_obj, hangarllm.ModelResponse)
            ## KWARGS
            assert isinstance(kwargs["model"], str)
            assert isinstance(kwargs["messages"], list) and isinstance(
                kwargs["messages"][0], dict
            )
            assert isinstance(kwargs["optional_params"], dict)
            assert isinstance(kwargs["hangarllm_params"], dict)
            assert isinstance(kwargs["start_time"], (datetime, type(None)))
            assert isinstance(kwargs["stream"], bool)
            assert isinstance(kwargs["user"], (str, type(None)))
            assert (
                isinstance(kwargs["input"], list)
                and isinstance(kwargs["input"][0], dict)
            ) or isinstance(kwargs["input"], (dict, str))
            assert isinstance(kwargs["api_key"], (str, type(None)))
            assert (
                isinstance(
                    kwargs["original_response"], (str, hangarllm.CustomStreamWrapper)
                )
                or inspect.isasyncgen(kwargs["original_response"])
                or inspect.iscoroutine(kwargs["original_response"])
            )
            assert isinstance(kwargs["additional_args"], (dict, type(None)))
            assert isinstance(kwargs["log_event_type"], str)
        except Exception:
            print(f"Assertion Error: {traceback.format_exc()}")
            self.errors.append(traceback.format_exc())

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            print(f"\n\nkwargs={kwargs}\n\n")
            print(
                json.dumps(kwargs, default=str)
            )  # this is a test to confirm no circular references are in the logging object

            self.states.append("sync_success")
            ## START TIME
            assert isinstance(start_time, datetime)
            ## END TIME
            assert isinstance(end_time, datetime)
            ## RESPONSE OBJECT
            assert isinstance(
                response_obj,
                (
                    hangarllm.ModelResponse,
                    hangarllm.EmbeddingResponse,
                    hangarllm.ImageResponse,
                ),
            )
            ## KWARGS
            assert isinstance(kwargs["model"], str)
            assert isinstance(kwargs["messages"], list) and isinstance(
                kwargs["messages"][0], dict
            )
            assert isinstance(kwargs["optional_params"], dict)
            assert isinstance(kwargs["hangarllm_params"], dict)
            assert isinstance(kwargs["hangarllm_params"]["api_base"], str)
            assert kwargs["cache_hit"] is None or isinstance(kwargs["cache_hit"], bool)
            assert isinstance(kwargs["start_time"], (datetime, type(None)))
            assert isinstance(kwargs["stream"], bool)
            assert isinstance(kwargs["user"], (str, type(None)))
            assert (
                isinstance(kwargs["input"], list)
                and (
                    isinstance(kwargs["input"][0], dict)
                    or isinstance(kwargs["input"][0], str)
                )
            ) or isinstance(kwargs["input"], (dict, str))
            assert isinstance(kwargs["api_key"], (str, type(None)))
            assert isinstance(
                kwargs["original_response"],
                (str, hangarllm.CustomStreamWrapper, BaseModel),
            ), "Original Response={}. Allowed types=[str, hangarllm.CustomStreamWrapper, BaseModel]".format(
                kwargs["original_response"]
            )
            assert isinstance(kwargs["additional_args"], (dict, type(None)))
            assert isinstance(kwargs["log_event_type"], str)
            assert isinstance(kwargs["response_cost"], (float, type(None)))
        except Exception:
            print(f"Assertion Error: {traceback.format_exc()}")
            self.errors.append(traceback.format_exc())

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            print(f"kwargs: {kwargs}")
            self.states.append("sync_failure")
            ## START TIME
            assert isinstance(start_time, datetime)
            ## END TIME
            assert isinstance(end_time, datetime)
            ## RESPONSE OBJECT
            assert response_obj == None
            ## KWARGS
            assert isinstance(kwargs["model"], str)
            assert isinstance(kwargs["messages"], list) and isinstance(
                kwargs["messages"][0], dict
            )

            assert isinstance(kwargs["optional_params"], dict)
            assert isinstance(kwargs["hangarllm_params"], dict)
            assert isinstance(kwargs["hangarllm_params"]["metadata"], Optional[dict])
            assert isinstance(kwargs["start_time"], (datetime, type(None)))
            assert isinstance(kwargs["stream"], bool)
            assert isinstance(kwargs["user"], (str, type(None)))
            assert (
                isinstance(kwargs["input"], list)
                and isinstance(kwargs["input"][0], dict)
            ) or isinstance(kwargs["input"], (dict, str))
            assert isinstance(kwargs["api_key"], (str, type(None)))
            assert (
                isinstance(
                    kwargs["original_response"], (str, hangarllm.CustomStreamWrapper)
                )
                or kwargs["original_response"] == None
            )
            assert isinstance(kwargs["additional_args"], (dict, type(None)))
            assert isinstance(kwargs["log_event_type"], str)
        except Exception:
            print(f"Assertion Error: {traceback.format_exc()}")
            self.errors.append(traceback.format_exc())

    async def async_log_pre_api_call(self, model, messages, kwargs):
        try:
            self.states.append("async_pre_api_call")
            ## MODEL
            assert isinstance(model, str)
            ## MESSAGES
            assert isinstance(messages, list) and isinstance(messages[0], dict)
            ## KWARGS
            assert isinstance(kwargs["model"], str)
            assert isinstance(kwargs["messages"], list) and isinstance(
                kwargs["messages"][0], dict
            )
            assert isinstance(kwargs["optional_params"], dict)
            assert isinstance(kwargs["hangarllm_params"], dict)
            assert isinstance(kwargs["start_time"], (datetime, type(None)))
            assert isinstance(kwargs["stream"], bool)
            assert isinstance(kwargs["user"], (str, type(None)))
        except Exception as e:
            print(f"Assertion Error: {traceback.format_exc()}")
            self.errors.append(traceback.format_exc())

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            print(
                "in async_log_success_event", kwargs, response_obj, start_time, end_time
            )
            self.states.append("async_success")
            ## START TIME
            assert isinstance(start_time, datetime)
            ## END TIME
            assert isinstance(end_time, datetime)
            ## RESPONSE OBJECT
            assert isinstance(
                response_obj,
                (
                    hangarllm.ModelResponse,
                    hangarllm.EmbeddingResponse,
                    hangarllm.TextCompletionResponse,
                ),
            )
            ## KWARGS
            assert isinstance(kwargs["model"], str)
            assert isinstance(kwargs["messages"], list)
            assert isinstance(kwargs["optional_params"], dict)
            assert isinstance(kwargs["hangarllm_params"], dict)
            assert isinstance(kwargs["hangarllm_params"]["api_base"], str)
            assert isinstance(kwargs["start_time"], (datetime, type(None)))
            assert isinstance(kwargs["stream"], bool)
            assert isinstance(kwargs["completion_start_time"], datetime)
            assert kwargs["cache_hit"] is None or isinstance(kwargs["cache_hit"], bool)
            assert isinstance(kwargs["user"], (str, type(None)))
            assert isinstance(kwargs["input"], (list, dict, str))
            assert isinstance(kwargs["api_key"], (str, type(None)))
            assert (
                isinstance(
                    kwargs["original_response"], (str, hangarllm.CustomStreamWrapper)
                )
                or inspect.isasyncgen(kwargs["original_response"])
                or inspect.iscoroutine(kwargs["original_response"])
            )
            assert isinstance(kwargs["additional_args"], (dict, type(None)))
            assert isinstance(kwargs["log_event_type"], str)
            assert kwargs["cache_hit"] is None or isinstance(kwargs["cache_hit"], bool)
            assert isinstance(kwargs["response_cost"], (float, type(None)))
        except Exception:
            print(f"Assertion Error: {traceback.format_exc()}")
            self.errors.append(traceback.format_exc())

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            self.states.append("async_failure")
            ## START TIME
            assert isinstance(start_time, datetime)
            ## END TIME
            assert isinstance(end_time, datetime)
            ## RESPONSE OBJECT
            assert response_obj == None
            ## KWARGS
            assert isinstance(kwargs["model"], str)
            assert isinstance(kwargs["messages"], list)
            assert isinstance(kwargs["optional_params"], dict)
            assert isinstance(kwargs["hangarllm_params"], dict)
            assert isinstance(kwargs["start_time"], (datetime, type(None)))
            assert isinstance(kwargs["stream"], bool)
            assert isinstance(kwargs["user"], (str, type(None)))
            assert isinstance(kwargs["input"], (list, str, dict))
            assert isinstance(kwargs["api_key"], (str, type(None)))
            assert (
                isinstance(
                    kwargs["original_response"], (str, hangarllm.CustomStreamWrapper)
                )
                or inspect.isasyncgen(kwargs["original_response"])
                or inspect.iscoroutine(kwargs["original_response"])
                or kwargs["original_response"] == None
            )
            assert isinstance(kwargs["additional_args"], (dict, type(None)))
            assert isinstance(kwargs["log_event_type"], str)
        except Exception:
            print(f"Assertion Error: {traceback.format_exc()}")
            self.errors.append(traceback.format_exc())
