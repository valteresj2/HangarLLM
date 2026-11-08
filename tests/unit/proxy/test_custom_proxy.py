import os
from typing import Final

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def build_app() -> FastAPI:
    load_dotenv()
    os.environ["SERVER_ROOT_PATH"] = "/my-custom-path"

    from hangarllm.proxy.proxy_server import app as hangarllm_app
    from hangarllm.proxy.proxy_server import proxy_startup_event

    app: Final = FastAPI(title="Custom HangarLLM Server", lifespan=proxy_startup_event)
    custom_path: Final = "/my-custom-path"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount(custom_path, hangarllm_app)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "message": "Welcome to the API Gateway",
            "hangarllm_endpoint": custom_path,
        }

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


if __name__ == "__main__":
    uvicorn.run(build_app(), host="0.0.0.0", port=4000, log_level="info")
