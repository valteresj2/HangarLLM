import json

import pytest
from fastapi.testclient import TestClient

from unittest.mock import MagicMock, patch

from hangarllm import rerank
from hangarllm.llms.custom_httpx.http_handler import HTTPHandler
