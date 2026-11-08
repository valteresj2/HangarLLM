import requests


def get_initial_config():
    proxy_base_url = input("Enter your proxy base URL (e.g., http://localhost:4000): ")
    master_key = input("Enter your HANGARLLM_MASTER_KEY ")
    return proxy_base_url, master_key


def get_user_input():
    model_name = input(
        "Enter model_name (this is the 'model' passed in /chat/completions requests):"
    )
    model = input("hangarllm_params: Enter model eg. 'azure/<your-deployment-name>': ")
    tpm = int(input("hangarllm_params: Enter tpm (tokens per minute): "))
    rpm = int(input("hangarllm_params: Enter rpm (requests per minute): "))
    api_key = input("hangarllm_params: Enter api_key: ")
    api_base = input("hangarllm_params: Enter api_base: ")
    api_version = input("hangarllm_params: Enter api_version: ")
    timeout = int(input("hangarllm_params: Enter timeout (0 for default): "))
    stream_timeout = int(
        input("hangarllm_params: Enter stream_timeout (0 for default): ")
    )
    max_retries = int(input("hangarllm_params: Enter max_retries (0 for default): "))

    return {
        "model_name": model_name,
        "hangarllm_params": {
            "model": model,
            "tpm": tpm,
            "rpm": rpm,
            "api_key": api_key,
            "api_base": api_base,
            "api_version": api_version,
            "timeout": timeout,
            "stream_timeout": stream_timeout,
            "max_retries": max_retries,
        },
    }


def make_request(proxy_base_url, master_key, data):
    url = f"{proxy_base_url}/model/new"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {master_key}",
    }

    response = requests.post(url, headers=headers, json=data)

    print(f"Status Code: {response.status_code}")
    print(f"Response from adding model: {response.text}")


def main():
    proxy_base_url, master_key = get_initial_config()

    while True:
        print("Adding new Model to your proxy server...")
        data = get_user_input()
        make_request(proxy_base_url, master_key, data)

        add_another = input("Do you want to add another model? (yes/no): ").lower()
        if add_another != "yes":
            break

    print("Script finished.")


if __name__ == "__main__":
    main()
