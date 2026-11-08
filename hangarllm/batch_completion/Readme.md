# Implementation of `hangarllm.batch_completion`, `hangarllm.batch_completion_models`, `hangarllm.batch_completion_models_all_responses`

Doc: https://github.com/valteresj2/HangarLLM#readme


HangarLLM Python SDK allows you to:
1. `hangarllm.batch_completion` Batch hangarllm.completion function for a given model.
2. `hangarllm.batch_completion_models` Send a request to multiple language models concurrently and return the response
    as soon as one of the models responds.
3. `hangarllm.batch_completion_models_all_responses` Send a request to multiple language models concurrently and return a list of responses
    from all models that respond.