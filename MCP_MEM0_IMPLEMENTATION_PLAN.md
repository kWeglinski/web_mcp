# Implementation Plan: Privacy-First, Dockerized MCP Server with Mem0

## 1. Project Overview
The objective is to build a **Model Context Protocol (MCP) Server** that provides long-term, personalized memory to LLMs using the **Mem0** framework. 

### Core Constraints
* **Zero-Cloud Policy:** No data (embeddings, text, or vectors) may leave the local machine.
* **OpenAI-Compatible API:** The LLM reasoning layer will connect to a local OpenAI-compatible endpoint (e.g., LM Studio, vLLM) via standard protocols.
* **Containerized:** The entire server must run inside a Docker container.
* **Fully Configurable:** All model names, API URLs, and paths must be injectable via Docker environment variables.
* **Persistent:** Memories must persist across container restarts using Docker Volumes.

---

## 2. Architecture
The system uses a "Hybrid Local Stack" to bridge the gap between ease of use and absolute privacy.

```text
[ LLM Client ] <--- (stdio) ---> [ Docker Container: MCP Server ]
                                        |
        ________________________________|________________________________
       |                                |                                |
[ LLM Layer ]                 [ Embedding Layer ]              [ Vector Store ]
(OpenAI-compatible)           (Local Transformers)             (Local ChromaDB)
      |                                |                                |
[ Local API Server ]          [ Python Process ]               [ Local Disk/Volume ]
(LM Studio / vLLM)            (HuggingFace/Sentence-T)         (./chroma_db)
```

---

## 3. Technical Stack
* **Orchestration:** [Model Context Protocol (MCP) Python SDK](https://github.com/modelcontextprotocol/python-sdk).
* **Memory Framework:** [Mem0](https://github.com/mem0ai/mem0).
* **Vector Database:** [ChromaDB](https://www.trychroma.com/) (running locally inside the container).
* **Embeddings:** `sentence-transformers` via `langchain-huggingface` (executes in the Python process).
* **LLM Provider:** Any local OpenAI-compatible server (LM Studio, vLLM, LocalAI).
* **Containerization:** Docker & Docker Compose.

---

## 4. Implementation Roadmap

### Phase 1: Development of the Core Server (`server.py`)
Develop the Python application logic with a focus on dynamic configuration.

1. **Dynamic Config Loading**: Use `os.getenv` to build the `Mem0` configuration dictionary.
2. **The "Hybrid" Setup**: 
    * Set `llm.provider` to `"openai"` but point `base_url` to the local host.
    * Set `embedder.provider` to `"langchain"` to ensure embeddings run locally via HuggingFace instead of calling an API.
3. **Tool Definition**: Implement three high-level tools:
    * `add_memory(user_id, content)`: Extracts and stores facts.
    * `search_memory(user_id, query)`: Performs semantic retrieval.
    * `get_user_memories(user_id)`: Provides a full history for the user.
4. **Transport**: Use `mcp.run(transport="stdio")`.

### Phase 2: Containerization (`Dockerfile` & `docker-compose.yml`)
Wrap the application for portable, environment-controlled deployment.

1. **Dockerfile**:
    * Use `python:3.12-slim` as the base.
    * Install system dependencies for `chromadb` and `sentence-transformers`.
    * Install Python requirements via `pip` or `uv`.
2. **Docker Compose**:
    * Define the service and environment variables.
    * **Persistence**: Map a host directory `./chroma_db` to the container's `/app/chroma_db`.
    * **Networking**: Ensure `host.docker.internal` is accessible to reach the LLM API on the host machine.

### Phase 3: Integration & Testing
1. **Local Validation**: Run `docker-compose up` and verify the server starts without attempting any outbound network calls.
2. **Client Connection**: Update `claude_desktop_config.json` to use the `docker run` command as the MCP server execution path.
3. **Memory Lifecycle Test**: 
    * "Remember I like espresso." $\rightarrow$ Check `chroma_db` folder for new files.
    * Restart container $\rightarrow$ "What is my coffee preference?" $\rightarrow$ Verify retrieval.

---

## 5. Detailed Specifications

### Environment Variable Schema
The following variables must be provided to the container:

| Variable | Description | Required | Default (Fallback) |
| :--- | :--- | :--- | :--- |
| `MEM0_LLM_MODEL` | Name of the model in your local API | Yes | `llama3:8b` |
| `MEM0_BASE_URL` | Local API URL (use `host.docker.internal`) | Yes | `http://host.docker.internal:1234/v1` |
| `MEM0_EMBED_MODEL`| HuggingFace model for local embeddings | Yes | `BAAI/bge-small-en-v1.5` |
| `MEM0_API_KEY` | Dummy key for OpenAI-compatibility | Yes | `local-secret` |
| `MEM0_CHROMA_PATH` | Internal path for DB persistence | No | `./chroma_db` |

### Tool Schemas (Input/Output)
| Tool | Input Schema (JSON) | Expected Output |
| :--- | :--- | :--- |
| `add_memory` | `{"user_id": "str", "content": "str"}` | `"Memory added successfully"` |
| `search_memory`| `{"user_id": "str", "query": "str"}` | List of relevant memory snippets |
| `get_memories` | `{"user_id": "str"}` | Full list of user-specific facts |

---

## 6. Privacy & Verification Audit
To confirm the "Zero-Cloud" status, perform these three checks:
1. **Dependency Check**: Ensure `langchain-huggingface` is used so no embedding API calls are made.
2. **Network Monitor**: Run `tcpdump` or a similar tool while interacting with the LLM to verify no traffic is directed toward `api.openai.com` or similar domains.
3. **Persistence Check**: Verify that the `./chroma_db` folder on your host machine grows in size as you add memories.
