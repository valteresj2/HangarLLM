# Caching on HangarLLM

HangarLLM supports multiple caching mechanisms. This allows users to choose the most suitable caching solution for their use case.

The following caching mechanisms are supported:

1. **RedisCache**
2. **RedisSemanticCache**
3. **QdrantSemanticCache**
4. **InMemoryCache**
5. **S3Cache**
6. **AzureBlobCache**
7. **DualCache** (updates both Redis and an in-memory cache simultaneously)

## Folder Structure

```
hangarllm/caching/
├── base_cache.py
├── caching.py
├── caching_handler.py
├── dual_cache.py
├── in_memory_cache.py
├── qdrant_semantic_cache.py
├── redis_cache.py
├── redis_semantic_cache.py
├── s3_cache.py
```

## Documentation
- [Caching on HangarLLM Gateway](https://github.com/valteresj2/HangarLLM#readme)
- [Caching on HangarLLM Python](https://github.com/valteresj2/HangarLLM#readme)







