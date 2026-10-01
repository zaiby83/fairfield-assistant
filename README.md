# fairfield-assistant

**Fairfield AI Assistant**: an internal AI chat assistant for City of Fairfield (CA) staff, run by TSS.
**Status: DEV.** The bring-up has not been run end to end yet. Sections marked _TBD_ get filled in once results are known.

## Architecture

```
 Browser (Mac, http://localhost:3080)
   │
   ▼
 gateway (socat) ── the only container with ports or a route off the Docker host
   │
   ▼  ┌──────────── compose "default" network, internal: true (no internet) ────────────┐
 LibreChat v0.8.8 (api) ── mongodb, meilisearch, vectordb, rag_api ── ollama (nomic-embed-text)
   │  custom endpoint "Fairfield AI", key = LITELLM_MASTER_KEY
   ▼
 LiteLLM proxy v1.103.2  ("litellm:4000" inside compose; 127.0.0.1:4000 on Mac via gateway)
   │  fairfield-general → hosted_vllm/gpt-oss-120b   key = VLLM_API_KEY
   │  fairfield-vision  → hosted_vllm/gemma4-26b
   ▼  gateway:8000/8001 → direct Ethernet 192.168.250.0/30 (Mac en8 .2 ↔ Spark enP7s7 .1)
 DGX Spark (GB10), image vllm-node (eugr/spark-vllm)
   ├─ vllm-gptoss  openai/gpt-oss-120b            192.168.250.1:8000  gpu-mem 0.65, ctx 64k
   └─ vllm-gemma   nvidia/Gemma-4-26B-A4B-NVFP4   192.168.250.1:8001  gpu-mem 0.22, ctx 32k (text+image)
```

Nothing binds `0.0.0.0` on a host interface. vLLM listens only on the direct-link address. The gateway publishes LibreChat (3080), the admin panel (3000) and LiteLLM (4000) only on the Mac's loopback.

## Air gap (CJIS)

No City data may leave the City, and no component may call an external service.

- **Network:** every compose service is on the `default` network, which is `internal: true`. The only exception is `gateway`. It also joins `egress` and runs fixed socat forwards: loopback ports in, and `gateway:8000/8001 → 192.168.250.1` out. Nothing else is forwarded.
- **Document search:** `rag_api` embeds with the local `ollama` service (`EMBEDDINGS_PROVIDER=ollama`, `OLLAMA_NO_CLOUD=1`). It never uses OpenAI.
- **No phone-home:** vLLM runs with `VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1`, `HF_HUB_OFFLINE=1` and `HF_HUB_DISABLE_TELEMETRY=1`. LiteLLM runs with `LITELLM_LOCAL_MODEL_COST_MAP=True` and `--telemetry False`. Meilisearch runs with `MEILI_NO_ANALYTICS=true`.
- **No cloud providers:** `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_KEY` and `ASSISTANTS_API_KEY` are blank in `LibreChat/.env`.
- **New images and models:** nothing in the stack can pull. Pull on a networked machine, then `docker save | docker load` them onto the Mac, and copy Ollama models into `LibreChat/ollama_data/models`. Images that aren't pulled by the stack use `pull_policy: never`.
- **Check egress:** from any container except `gateway`, `bash -c 'exec 3<>/dev/tcp/1.1.1.1/443'` must fail. See CHANGELOG ("Air gap for CJIS") for the full check.
- **Still open:** the Spark is on COF-P Wi-Fi with an internet route, and the Mac uses a hotspot. The containers can't use either route, but the hosts themselves can.

### Approved exception: two public City sites (read-only)

Approved by the user on 2026-10-01. TSS should approve it in writing before production. The Fairfield Assistant model spec can read **www.fairfield.ca.gov** and **pub-fairfield.escribemeetings.com**, and nothing else.

```
 api ──(MCP, pinned to the spec)──► city-web ──► webproxy (Squid) ──► those two sites only
       [default, internal]           [default + webtools]   [webtools + egress]
```

- **`city-web`** (`frontend/city-web/server.py`) is an MCP server with three tools: `search_meeting_documents` (eScribe search), `find_in_document` and `read_city_page`. It allows only https URLs on the two hosts and checks every redirect. It is GET-only, apart from the eScribe search endpoint. It identifies itself honestly (`FairfieldAIAssistant/1.0`) and **never works around bot protection**.
- **`webproxy`** allows only `CONNECT :443` to the two hosts and refuses everything else. It strips `X-Forwarded-For`/`Via`. Only `city-web` can reach it, via the internal `webtools` network.
- **Audit logs:**
  - `LibreChat/logs/city-web/audit.jsonl`: time, LibreChat user email, tool, exact URL or search text, outcome.
  - `LibreChat/logs/webproxy/access.log`: every connection, allowed or denied.
- **What leaves the City:** only the URL or search words the tool sends. The prompt tells the model never to search with names or confidential details.
- **LibreChat settings this needs:**
  - `interface.mcpServers.use: true`, because the USE permission gates even operator-pinned MCP tools. `create`, `share` and `public` stay `false`.
  - `chatMenu: false`, which keeps city-web out of the picker.
  - `requestHeaders`, not `headers`, for the user placeholder. A placeholder in `headers` makes LibreChat skip tool discovery.
- **Blocked by bot protection (needs the site operator):**
  - eScribe document downloads (`FileStream.ashx`, the agenda-package PDFs) sit behind a Cloudflare browser check and return 403. TSS can ask eScribe to allowlist the assistant. eScribe search and meeting agenda pages work.
  - fairfield.ca.gov (Akamai) currently accepts the tool. It blocks curl and headless browsers.
- **Rebuild city-web:** copy `frontend/city-web/` to the Spark, then run `docker build -t fairfield/city-web:<ver> .` and `docker save | docker load` onto the Mac. Bump the tag in the override.
- **Remove the exception:** delete the `city-web` and `webproxy` services, and the `mcpSettings`/`mcpServers` blocks and spec pin in `librechat.yaml`.

## Repository layout

| Path | Purpose |
|---|---|
| `spark/start-vllm.sh`, `spark/stop-vllm.sh` | vLLM container lifecycle. Copy them to `~/fairfield-assistant/spark/` on the Spark. |
| `frontend/librechat.yaml` | LibreChat config: endpoint, model specs, welcome text, acceptable-use modal. |
| `frontend/litellm-config.yaml` | LiteLLM model routing to the Spark. |
| `frontend/docker-compose.override.yml` | Adds the `litellm` service, pins images, binds ports to loopback. `LibreChat/docker-compose.override.yml` is a symlink to this file. |
| `frontend/LIBRECHAT_VERSION` | Pinned LibreChat tag, commit and image digest. |
| `LibreChat/` | Upstream clone. **Gitignored**, recreate it from `LIBRECHAT_VERSION`. |
| `.env` | Project secrets (`VLLM_API_KEY`). **Gitignored.** |
| `LibreChat/.env` | LibreChat secrets plus `LITELLM_MASTER_KEY`. **Gitignored.** |
| `CHANGELOG.md` | Every change made on either machine. |

**Why the clone is ignored rather than a submodule.** LibreChat's full history is large, and the Mac's internet is a cellular hotspot. A shallow clone at a pinned tag, recorded in `frontend/LIBRECHAT_VERSION`, gives the same reproducibility. All Fairfield-specific config lives in `frontend/`, so upgrading LibreChat means re-cloning at a new tag and bumping `version:` in `librechat.yaml`.

## Secrets

| Secret | Location | Used by |
|---|---|---|
| `VLLM_API_KEY` | Spark `~/vllm.env` (600); Mac `~/fairfield-assistant/.env` (600) | vLLM (read from the environment); LiteLLM via `env_file` |
| `LITELLM_MASTER_KEY` | `LibreChat/.env` | LibreChat → LiteLLM; LiteLLM `master_key` |
| `CREDS_KEY/IV`, `JWT_*`, `MEILI_MASTER_KEY`, `ADMIN_PANEL_SESSION_SECRET` | `LibreChat/.env` | LibreChat |

Never paste these into chat, tickets or commits. To rotate `VLLM_API_KEY`, update both files, then restart vLLM and LiteLLM.

## Bring-up

1. **Spark: models are cached.** `start-vllm.sh` refuses to start if any snapshot is missing or still has `*.incomplete` blobs.
2. **Spark: start vLLM** (over `ssh spark`):
   ```bash
   ~/fairfield-assistant/spark/start-vllm.sh
   ```
   Optional switches: `GEMMA_MTP=1` (MTP speculative decoding), `GPTOSS_MXFP4_FLAGS=1 GPTOSS_IMAGE=vllm-node-mxfp4` (only with the MXFP4 build).
   _TBD: observed load times and memory use._
3. **Mac: check vLLM from the Mac.** _TBD: exact curl check (reads the key from `.env` without echoing it)._
4. **Mac: start the frontend.** Pull the images on a fast network first (not the hotspot), then:
   ```bash
   cd ~/fairfield-assistant/LibreChat && docker compose up -d
   ```
5. Open http://localhost:3080, register (DEV only), accept the AUP modal, and test both model specs.
   _TBD: results._

## Teardown

```bash
cd ~/fairfield-assistant/LibreChat && docker compose down
```
```bash
ssh spark ~/fairfield-assistant/spark/stop-vllm.sh
```
`stop-vllm.sh` removes only the two vLLM containers. It leaves the HF cache, the image and `~/vllm.env` alone. `docker compose down` keeps LibreChat data in `LibreChat/data-node`, `meili_data_*` and the named volumes.

## Troubleshooting

- **vLLM container exits on start.** Run `ssh spark docker logs --tail 200 vllm-gptoss` (or `vllm-gemma`). _TBD: known failure modes._
- **Gemma fails with an out-of-memory error.** gpt-oss uses 0.55 of GPU memory, so 0.25 must still be free. Check that nothing else is using the GPU. _TBD_
- **gpt-oss has little KV cache.** About 61 GB of weights inside the 0.55 share leaves limited KV cache at 64k context. Check the "KV cache" line in the logs. _TBD: tune `GPTOSS_GPU_UTIL` or `GPTOSS_MAX_LEN`._
- **Both containers restart at once after a Spark reboot.** `--restart unless-stopped` gives no start ordering. If Gemma fails, run `stop-vllm.sh` then `start-vllm.sh`. _TBD_
- **LibreChat shows no models, or 401s.** Check that `LITELLM_MASTER_KEY` starts with `sk-`, and check `docker logs litellm`.
- **LiteLLM can't reach the Spark.** From the Mac: `nc -vz 192.168.250.1 8000`. Check that `en8` is up.
- _TBD_
