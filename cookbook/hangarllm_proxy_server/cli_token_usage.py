#!/usr/bin/env python3
"""
Example: Using CLI token with HangarLLM SDK

This example shows how to use the CLI authentication token
in your Python scripts after running `lite login`.
"""

from textwrap import indent
import hangarllm

HANGARLLM_BASE_URL = "http://localhost:4000/"


def main():
    """Using CLI token with HangarLLM SDK"""
    print("🚀 Using CLI Token with HangarLLM SDK")
    print("=" * 40)
    # hangarllm._turn_on_debug()

    # Get the CLI token
    api_key = hangarllm.get_hangarllm_gateway_api_key()

    if not api_key:
        print("❌ No CLI token found. Please run 'lite login' first.")
        return

    print("✅ Found CLI token.")

    available_models = hangarllm.get_valid_models(
        check_provider_endpoint=True,
        custom_llm_provider="hangarllm_proxy",
        api_key=api_key,
        api_base=HANGARLLM_BASE_URL,
    )

    print("✅ Available models:")
    if available_models:
        for i, model in enumerate(available_models, 1):
            print(f"   {i:2d}. {model}")
    else:
        print("   No models available")

    # Use with HangarLLM
    try:
        response = hangarllm.completion(
            model="hangarllm_proxy/gemini/gemini-2.5-flash",
            messages=[{"role": "user", "content": "Hello from CLI token!"}],
            api_key=api_key,
            base_url=HANGARLLM_BASE_URL,
        )
        print(f"✅ LLM Response: {response.model_dump_json(indent=4)}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()

    print("\n💡 Tips:")
    print("1. Run 'lite login' to authenticate first")
    print("2. Replace 'https://your-proxy.com' with your actual proxy URL")
    print("3. The token is stored in your OS keychain, or in ~/.hangarllm/token.json when there is none")
