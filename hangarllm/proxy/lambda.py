from typing import Final

from mangum import Mangum

from hangarllm.proxy.proxy_server import app

handler: Final = Mangum(app, lifespan="on")
