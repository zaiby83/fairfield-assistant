# CHANGELOG — Fairfield Assistant (dev)

Every change made on either machine, newest last.

## 2026-10-01 — Phase 1: Preflight (Mac)
- [Mac] Verified (no change): git 2.50.1, Docker Compose v5.0.1, `ssh spark` key auth -> spark-5e7f,
  net.inet.ip.forwarding=0, en8 192.168.250.2/30 up 1000baseT, default route via en0 (hotspot 172.20.10.1).
- [Spark] Verified (no change): NetworkManager "mac-direct" active on enP7s7.
- [Mac] Started Docker Desktop (`open -a Docker`) — Docker Engine 29.1.5, VM: 14 CPUs / ~7.65 GiB RAM.
- [Mac] Created ~/fairfield-assistant/ and this CHANGELOG.md.

## 2026-10-01 — Phase 2: Spark recon
- [Spark] Read-only recon, no changes. GB10 cc 12.1, driver 580.173.02 / CUDA 13.0, Ubuntu 24.04.4,
  kernel 6.17.0-1031-nvidia, 121 GiB RAM, / 3.5 TB free, nvidia-ctk 1.20.0, Docker client 29.2.1.
  Findings: cof-local-admin not in `docker` group (socket permission denied); no HF cache yet; no internet (expected).
- [Mac] No changes.
- [Spark] Observed (not changed by me): Wi-Fi radio enabled, wlP9s9 joined "iPhone-D25DJNVTWM" hotspot
  (172.20.10.3, default route via wlP9s9). mac-direct (enP7s7) still active. Hotspot throughput measured at
  ~0.2–0.3 MB/s — too slow for ~96 GB of downloads. Decision: keep the Ethernet cable on the Mac (user, 2026-10-01).
- [Spark] User switched Wi-Fi at console: `sudo nmcli con up COF-P` -> wlP9s9 10.69.5.90, default via 10.69.4.1.
  mac-direct unaffected. Verified: huggingface.co 200, Docker Hub + nvcr.io reachable, HF download ~34.6 MB/s.

## 2026-10-01 — Phase 3: Downloads on Spark
- [Spark] User ran `sudo usermod -aG docker cof-local-admin` at console. Verified: docker client/server 29.2.1 without sudo.
- [Spark] Created ~/fairfield-logs/ (pull.log, download.log, download-models.sh).
- [Spark] Pulled eugr/spark-vllm:latest
  (sha256:ed1591f4fc71c44d236382ff8514ad9caba242d51369dfc75a07ddbc1c36dd30, 24.9 GB on disk), tagged `vllm-node`.
  Verified inside: vLLM 0.30.1rc1.dev511+gcb6458c5c, torch 2.13.0+cu130, `--gpus all` sees NVIDIA GB10 cc 12.1, hf 1.33.0.
- [Spark] Created ~/.cache/huggingface; started downloads (hf inside vllm-node, run as uid 1000, no host packages):
  openai/gpt-oss-120b (excluding original/*, metal/*), nvidia/Gemma-4-26B-A4B-NVFP4, google/gemma-4-26B-A4B-it-assistant.

## 2026-10-01 — Phase 4/5/7 prep (separate session)
Prep only: no containers started on either machine, no images pulled on the Mac, HF cache / downloads / ~/fairfield-logs / vllm-node image untouched.

Verified (no change):
- [Spark] Flags in `vllm serve --help=all` of vllm-node (ran help-only `docker run --rm --gpus all --entrypoint vllm vllm-node serve --help=all`
  plus a few short-lived `--rm` greps of the vLLM package; `--gpus` was needed because help fails with "Failed to infer device type" without it).
  Present: --tool-call-parser {openai,gemma4}, --reasoning-parser (openai_gptoss, gemma4 registered), --enable-auto-tool-choice,
  --enable-prefix-caching, --kv-cache-dtype fp8, --load-format (fastsafetensors 0.4.0, instanttensor 0.2.0 installed),
  --quantization mxfp4, --attention-backend FLASHINFER, --max-num-batched-tokens, --speculative-config (method "mtp", moe_backend "triton" valid),
  --served-model-name, --tensor-parallel-size, --api-key (vLLM also reads env VLLM_API_KEY, same enforcement).
  ABSENT in vllm-node (MXFP4-build only): --mxfp4-backend, --mxfp4-layers; env VLLM_USE_FLASHINFER_MOE_MXFP4_MXFP8 is unreferenced.
  Image entrypoint is /opt/nvidia/nvidia_entrypoint.sh, so scripts use `--entrypoint vllm`.
- Upstream recipes read from github.com/eugr/spark-vllm-docker main: recipes/openai-gpt-oss-120b.yaml, recipes/gemma4-26b-a4b-nvfp4.yaml.
- LibreChat latest release = v0.8.8 (published 2026-10-01T02:49Z; GitHub marks every LibreChat release "prerelease",
  so /releases/latest returns 404; v0.8.8 is the newest non-rc tag). Commit e8f3be08623663d4ad7f7241e693c94469b63bb0, librechat.example.yaml version 1.3.17.
  Image registry.librechat.ai/librechat-ai/librechat:v0.8.8 exists (sha256:5b706bce…, linux/arm64 + amd64), checked via `docker buildx imagetools inspect` (no pull).
- LiteLLM: ghcr.io/berriai/litellm:v1.103.2 (GitHub release 2026-10-01) = same digest as main-stable,
  sha256:f63fb81b831b170ec16851e23c36ac5bf52ef106b271406429524a2ed730bbfd, publishes linux/arm64 + amd64 (manifest only, no pull).
  Provider prefix hosted_vllm/ and `os.environ/VAR` + general_settings.master_key confirmed in docs.litellm.ai (providers/vllm, proxy/configs).
- LibreChat schema at v0.8.8 (packages/data-provider): modelSpecs.enforce/prioritize, spec fields name/label/default/description/preset,
  preset.promptPrefix/temperature/modelLabel, interface.customWelcome, interface.termsOfService.{externalUrl,openNewTab,modalAcceptance,modalTitle,modalContent},
  custom endpoint name/apiKey/baseURL/models.{default,fetch}/titleConvo/titleModel/modelDisplayLabel; CUSTOM_FOOTER env read by api/server/routes/config.js.

Changes:
- [Spark] Created ~/vllm.env (chmod 600) with a new VLLM_API_KEY (openssl rand -hex 32; not printed).
- [Spark] Created ~/fairfield-assistant/spark/ with start-vllm.sh, stop-vllm.sh (copied from Mac, sha256 verified). NOT run.
- [Mac] Created ~/fairfield-assistant/.env (chmod 600) with the same VLLM_API_KEY (match verified by hash).
- [Mac] spark/start-vllm.sh, spark/stop-vllm.sh: bash -n OK on Mac and Spark (bash 5.2). shellcheck not installed on either machine (not installed).
  Containers vllm-gptoss (:8000, 0.55, 64k) then vllm-gemma (:8001, 0.25, 32k, tp 1, no Ray), --host 192.168.250.1, HF_HUB_OFFLINE=1,
  key via --env-file (vLLM reads VLLM_API_KEY; key never on a command line). MXFP4-only flags behind GPTOSS_MXFP4_FLAGS=1 (refuses if image lacks them);
  MTP behind GEMMA_MTP=1. Preflight checks the bind IP, env-file perms, complete HF snapshots and existing containers.
- [Mac] Cloned LibreChat v0.8.8 (--depth 1) into ~/fairfield-assistant/LibreChat.
- [Mac] Created LibreChat/.env (chmod 600) from v0.8.8 .env.example: APP_TITLE, CUSTOM_FOOTER, ALLOW_REGISTRATION=true (dev), ALLOW_SOCIAL_LOGIN=false,
  fresh CREDS_KEY/CREDS_IV/JWT_SECRET/JWT_REFRESH_SECRET/MEILI_MASTER_KEY/ADMIN_PANEL_SESSION_SECRET, LITELLM_MASTER_KEY=sk-… (all random, not printed).
- [Mac] Created frontend/librechat.yaml, frontend/litellm-config.yaml, frontend/docker-compose.override.yml, frontend/LIBRECHAT_VERSION;
  symlink LibreChat/docker-compose.override.yml -> ../frontend/docker-compose.override.yml.
  Override: api image pinned to librechat:v0.8.8 (base file uses librechat-dev:latest), api and admin-panel ports changed to 127.0.0.1 (!override),
  litellm service pinned by tag@digest on 127.0.0.1:4000, VLLM_API_KEY via env_file ../.env, librechat.yaml mounted read-only.
- [Mac] `docker compose config --quiet` OK (only UID/GID-unset warnings from the base file); no service publishes on 0.0.0.0. Did not run up or pull.
- [Mac] git init (branch main) ~/fairfield-assistant; added .gitignore, README.md; files staged, NOT committed.
- [Mac] Installed shellcheck 0.11.0 via Homebrew (user approved). `shellcheck -x` on spark/*.sh: one SC2054 false positive
  (comma-separated --mxfp4-layers value) fixed by quoting "moe,qkv,o,lm_head"; now clean. Re-copied start-vllm.sh to the Spark (sha256 verified). Still NOT run.
- [Spark] Downloads complete 2026-10-01 13:57 PDT (~36 min, 80 GiB in ~/.cache/huggingface/hub, 0 incomplete blobs):
  openai/gpt-oss-120b rev b5c939de8f754692c1647ca79fbf85e8c1e70f8a (65.28 GB, 15 safetensors)
  nvidia/Gemma-4-26B-A4B-NVFP4 rev a19cfe00be84568a6867111c9a68c9c44fdcffe6 (18.83 GB, 2 safetensors)
  google/gemma-4-26B-A4B-it-assistant rev 6e5aaaf4c42b98394530b8fda2e95cadd65c151c (0.87 GB)
  Disk: / 138G used, 3.4T free.

## 2026-10-01 — Phase 4: Spark serving (taken over in main session)
- [Spark] Reviewed spark/start-vllm.sh + stop-vllm.sh from the prep session; sha256 Mac == Spark. Ran start-vllm.sh 13:59 (log ~/fairfield-logs/start-vllm.log).
- [Spark] vllm-gptoss FAILED at --gpu-memory-utilization 0.55: weights 66.14 GiB; "Available KV cache memory" -8.65 GiB (cold) / -4.46 GiB (warm restart).
  Container crash-looped under --restart unless-stopped; stopped + removed with stop-vllm.sh (14:0x). Gemma never started. No other changes.
- [Mac] spark/start-vllm.sh (user approved): GPTOSS_GPU_UTIL 0.55->0.65, GEMMA_GPU_UTIL 0.25->0.22; mount ~/.cache/vllm and
  ~/.cache/flashinfer (paths verified in image: VLLM_CACHE_ROOT=/root/.cache/vllm, FlashInfer JIT /root/.cache/flashinfer/...);
  on failure/restart before ready: save full log to ~/fairfield-logs/<name>-failed-<ts>.log and `docker rm -f` the container.
  bash -n + shellcheck clean; copied to Spark (sha256 9c78613861520c95… both sides).
- [Spark] Created ~/.cache/vllm, ~/.cache/flashinfer (by script). Ran start-vllm.sh 14:04:
  vllm-gptoss ready 110s — weights 66.14 GiB, KV 4.26 GiB = 198,013 tokens (3.02x @ 65,536).
  vllm-gemma  ready 150s — weights 18.16 GiB, KV 3.39 GiB = 56,291 tokens (1.72x @ 32,768). Host RAM available after: ~9 GiB.
- [Verify from Mac] Listening only on 192.168.250.1:8000/:8001 (ss). No key -> 401; with key -> gpt-oss-120b (65536), gemma4-26b (32768).
  Single-stream decode: gpt-oss-120b ~35 tok/s (TTFT ~0.2s); gemma4-26b ~30 tok/s (TTFT ~0.1s). Gemma vision PASS (red/blue test PNG described correctly).

## 2026-10-01 — City of Fairfield branding (Mac)
- [Mac] New frontend/branding/: City seal as logo.svg, favicons, apple-touch/192/maskable icons (from the City's
  seal artwork, cropped/resized with sips); manifest.webmanifest renamed "Fairfield AI Assistant", theme #188446.
- [Mac] fairfield-theme.css: green theme (#188446, sampled from the seal; white on it 4.7:1) overriding LibreChat
  v0.8.8 CSS variables in light + dark, plus #send-button (painted with bg-text-primary, not --surface-submit).
- [Mac] docker-compose.override.yml: bind-mount the branding files over client/dist; api `command` patches
  index.html at start (theme <link> with ?v=<cksum> cache-buster, <title>, theme-color) then `npm run backend`.
  No image rebuild. Re-check the variable names when upgrading past v0.8.8.
- [Mac] librechat.yaml: iconURL /assets/icon-192x192.png on the endpoint and both model specs.
- [Mac] Recreated LibreChat (`docker compose up -d --force-recreate api`); verified served assets match, theme
  applied in light and dark, send button green. Committed f400da2.

## 2026-10-01 — Air gap for CJIS (session "Internet connectivity check")
Requirement (user): purely in-house, nothing hits an external service, no City data leaves the City.

Found (before):
- [Mac] rag_api embeddings defaulted to OpenAI (`OpenAIEmbeddings` in its log; OPENAI_API_KEY=user_provided). Uploaded
  file-search text would have been sent to api.openai.com. Uploads dir was empty, so nothing had been embedded yet.
- [Spark] vllm-gptoss and vllm-gemma were sending vLLM usage reports to stats.vllm.ai (hardware/config/model, a UUID;
  no prompts). /root/.config/vllm/usage_stats.json written at 21:24/21:26 UTC.
- [Mac] LiteLLM fetches its model cost map from raw.githubusercontent.com at startup.
- [Mac] Every container could reach the internet over the Mac's hotspot.

Changes:
- [Mac] spark/start-vllm.sh: common_run_args add VLLM_NO_USAGE_STATS=1, DO_NOT_TRACK=1, HF_HUB_DISABLE_TELEMETRY=1.
  bash -n + shellcheck clean; copied to Spark (sha256 4592d0d398b7b2a5… both sides).
- [Spark] stop-vllm.sh + start-vllm.sh 14:37: vllm-gptoss ready 70s, vllm-gemma ready by 14:40. Verified that all 4 env
  switches are set in both containers and no usage_stats.json is written.
- [Spark] Pulled ollama/ollama@sha256:2a6e883b…5d01 (0.35.0) and alpine/socat@sha256:5ffbd6ae…732f (1.8.1.3) on COF-P,
  pulled nomic-embed-text (274 MB) in a temporary container, then copied images (docker save | docker load) and
  model files (models/ only, no Ollama identity key) to the Mac over the direct cable. Removed the staging dir and both images from the Spark.
- [Mac] frontend/docker-compose.override.yml:
  compose `default` network is now `internal: true` (no route off the Docker host);
  new `gateway` (socat) is the only service on `egress` and the only one publishing ports:
  127.0.0.1:3080/3000/4000 -> api/admin-panel/litellm, and gateway:8000/8001 -> 192.168.250.1:8000/8001 only.
  api/admin-panel ports removed (`!reset []`); litellm port removed, `--telemetry False`, LITELLM_LOCAL_MODEL_COST_MAP=True;
  new `ollama` service (OLLAMA_NO_CLOUD=1, models in LibreChat/ollama_data); admin-panel and rag_api pinned by digest
  (were :latest); rag_api depends_on ollama.
- [Mac] frontend/litellm-config.yaml: api_base -> http://gateway:8000/v1 and :8001/v1.
- [Mac] LibreChat/.env (backup: LibreChat/.env.bak-pre-airgap, 600): OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_KEY,
  ASSISTANTS_API_KEY blanked (were user_provided); HELP_AND_FAQ_URL=/ (was https://librechat.ai);
  added EMBEDDINGS_PROVIDER=ollama, EMBEDDINGS_MODEL=nomic-embed-text, OLLAMA_BASE_URL=http://ollama:11434.
- [Mac] `docker compose down && up -d`.

Verified (after):
- From LibreChat, admin-panel, litellm, rag_api, ollama, chat-mongodb, vectordb: 1.1.1.1:443, api.openai.com:443 and
  192.168.250.1:8000 are all blocked. chat-meilisearch has no probe tool but is on the same internal-only network.
- rag_api log: `OllamaEmbeddings`; Ollama log: "Ollama cloud disabled: true".
- A synthetic test document went through rag_api /embed -> /query (correct chunk returned) -> /documents delete.
- Through the gateway: fairfield-general and fairfield-vision both answered a test chat; UI :3080 and admin panel :3000 return 200.

Still open (not changed here; needs the user, or is out of scope):
- [Spark] is still on COF-P Wi-Fi with a default route to the internet (used for the model downloads), and Firefox
  is open on its desktop with a live outbound connection. To air-gap it: `sudo nmcli con down COF-P` at the console.
- [Mac] still uses the cellular hotspot for its own traffic. The containers are isolated from it; the Mac itself is not.
- Ingress goes through socat, so LibreChat sees every client as the gateway IP (per-IP rate limits/bans are shared).

## 2026-10-01 — Staff UI lockdown (session "fairfield-chatbot")
Goal: staff see only chat, the model picker (the two modelSpecs) and file uploads. Air-gap settings above untouched.

Changes:
- [Mac] frontend/librechat.yaml:
  `interface`: modelSelect, fileSearch, fileCitations true; endpointsMenu, sidePanel, agents, prompts, bookmarks, memories,
  presets, parameters, multiConvo, temporaryChat, runCode, webSearch, skills, sharedLinks false;
  marketplace.use, mcpServers.use false; schedules.use/create false (the boolean `schedules: false` did not update the roles).
  `endpoints.agents.disableBuilder: true`.
  New `fileConfig`: 10 files / 25 MB each / 100 MB per message, serverFileSizeLimit 100 MB;
  types pdf, text/*, Office OpenXML, msword, image/* (image/* needed by fairfield-vision).
- [Mac] LibreChat/.env: added `ENDPOINTS=custom` (after the commented example, line ~404); ALLOW_SHARED_LINKS true -> false.
- [Mac] `docker compose up -d api` (this also recreated rag_api, which reads .env) then `docker compose restart api` x3.
- [Mac] Ran a throwaway `docker run --rm --network none ruby:alpine` to parse the YAML. This pulled ruby:alpine from Docker Hub
  onto the Mac host (outside the stack). Image removed straight after. Don't do this again: host Docker can still reach the internet.

Verified (after):
- api log: custom config loaded, server listening, readiness checks passing; role updates logged for MCP_SERVERS, SKILLS,
  SHARED_LINKS and SCHEDULES.
- Mongo `roles` (USER and ADMIN): AGENTS, PROMPTS, BOOKMARKS, MEMORIES, MULTI_CONVO, TEMPORARY_CHAT, RUN_CODE, WEB_SEARCH,
  MARKETPLACE, MCP_SERVERS, SKILLS.USE, SCHEDULES, SHARED_LINKS all false; FILE_SEARCH and FILE_CITATIONS true.
- An already-logged-in client got 403 on /api/agents and /api/tags (bookmarks), so the server enforces it, not just the UI.
- `/app/.env` in the api container shows ENDPOINTS=custom and ALLOW_SHARED_LINKS=false.

Still open:
- Not yet checked in a browser as a normal (non-admin) user.
- Startup warning: modelSpecs.enforce "can conflict with" modelSelect. Expected: staff choose only between the two specs.
- Already in the logs before this change: METRICS_SECRET unset; scheduler not started (no Redis). Schedules are now disabled anyway.
- Acceptable-use text in librechat.yaml says not to enter CJI, which conflicts with the CJIS work. Needs a policy decision.

## 2026-10-01 — Brand & Style Guide theme (Mac)
- [Mac] Retheme to the City's Brand & Style Guide 2023 (~/Documents/Brand  Style Guide_2023.pdf), replacing the
  seal-sampled green #188446 (not in the official palette). User chose Royal Blue as the main color.
- [Mac] fairfield-theme.css: Royal Blue #365F9F for send button, links, focus, selected chat (white on it 6.4:1);
  light mode sidebar 15% Cream, hover Light Moss, Moss Green #AAB058 rule under the top bar, Cream text selection,
  Forest Green #187019 for success. Dark mode: Royal Blue buttons, links 143 160 210 (7:1), white edge around the
  seal (guide: white-edge logo on dark; CSS stand-in until MOD supplies the artwork). Goldenrod unused (fails
  contrast as text).
- [Mac] Fonts per guide: Calibri body, Book Antiqua welcome line, local fonts only (fallbacks Carlito/Segoe UI,
  Palatino). Nothing downloaded; fonts not redistributed.
- [Mac] theme-color #365f9f in manifest.webmanifest and the index.html patch in docker-compose.override.yml.
- [Mac] Recreated LibreChat; checked light + dark in the browser.

## 2026-10-01 — Approved exception: read-only access to two City sites (session "Internet connectivity check")
Requirement (user): the assistant must be able to read the City website. User chose: only www.fairfield.ca.gov and
pub-fairfield.escribemeetings.com, read-only, logged. Everything else stays air-gapped.

Findings:
- www.fairfield.ca.gov (Akamai) returns 403 to curl (default and browser User-Agent, from both hotspot and City
  egress 50.201.161.6) and to headless Chromium (Playwright 1.63, tested on the Spark, image removed afterwards).
  It returned 200 to the city-web tool's honest User-Agent `FairfieldAIAssistant/1.0 (City of Fairfield TSS; read-only)`.
- eScribe: search (`POST /GetSearchData.asmx/GetSearchMeetingData`) and Meeting.aspx pages work. Document downloads
  (`FileStream.ashx`, agenda-package PDFs) sit behind a Cloudflare "Verifying your browser" check (403). Not worked around;
  the tool returns a message telling the user to open the link, and telling TSS to ask eScribe to allowlist the assistant.

Changes:
- [Mac] New frontend/city-web/: server.py (MCP server, mcp 2.2.0 MCPServer, streamable HTTP, stateless; tools
  search_meeting_documents / find_in_document / read_city_page; host allowlist + per-redirect re-check, https only,
  GET only apart from the eScribe search endpoint, 100 MB cap, JSONL audit log with the X-LibreChat-User header),
  Dockerfile (python:3.13-slim, non-root uid 10001), requirements.txt (pinned from pip freeze), squid.conf
  (CONNECT :443 to the two hosts only, forwarded_for delete, via off, no cache, access log).
- [Spark] Built fairfield/city-web:1.0 in ~/fairfield-build/city-web; pulled
  ubuntu/squid@sha256:6a097f68…e029 (Squid 6.13, tagged ubuntu/squid:6.13-24.04); functional test on a scratch
  network (search, agenda page, fairfield.ca.gov page, blocked example.com / http:// / look-alike host); removed
  test containers, network and the :dev image. Both images moved to the Mac with docker save | docker load.
- [Mac] frontend/docker-compose.override.yml: new internal network `webtools`; new services `city-web`
  (default + webtools, HTTPS_PROXY=http://webproxy:3128, logs -> LibreChat/logs/city-web) and `webproxy`
  (webtools + egress, squid.conf mounted read-only, logs -> LibreChat/logs/webproxy); api depends_on city-web.
- [Mac] frontend/librechat.yaml: mcpSettings.allowedAddresses [city-web:8000]; mcpServers.city-web
  (streamable-http, chatMenu false, serverInstructions, timeout 180 s, requestHeaders X-LibreChat-User =
  {{LIBRECHAT_USER_EMAIL}}); spec fairfield-assistant pins mcpServers [city-web]; its promptPrefix now describes the two
  sites, forbids confidential search terms, and says to give the link when a site refuses;
  interface.mcpServers use false -> true with create/share/public false.
- Debugging, in order: (1) `headers` with a user placeholder made LibreChat skip tool discovery at startup, fixed by
  using `requestHeaders`. (2) interface.mcpServers.use:false removes the MCP_SERVERS USE permission, which filters out
  even spec-pinned tools (ToolService.js canUseServers), fixed by setting use: true. While the pin was failing, General chats returned
  "configured to use MCP tools, but none are available" (seen for 2 users around 22:02–22:05 UTC); the pin was removed
  within minutes each time until fixed.

Verified:
- Browser chat as the test user: the model called search_meeting_documents ×4, read_city_page ×3 and find_in_document ×1. The audit log
  records each call with the user's email, and the Squid log shows only pub-fairfield.escribemeetings.com:443 CONNECTs.
  The answer correctly reported the Dec 2 2025 item 12.1/L.1 "Measure P Oversight Committee Annual Report", but it also
  produced table rows with placeholder links ("Id=??") that the tools didn't provide. Model reliability on tool results
  still needs work.
- city-web cannot connect directly (1.1.1.1, www.fairfield.ca.gov, 192.168.250.1 all blocked); via the proxy,
  example.com and www.google.com get 403 and are logged TCP_DENIED; the api container cannot reach webproxy.

## 2026-10-01 — City website look + mode picker (Mac)
- [Mac] Modelled on fairfield.ca.gov (user: "still looks very AI"). fairfield-theme.css + new branding/fairfield.js
  (a <script defer> added to index.html by the api command, same ?v=<cksum of css+js> cache-buster as the CSS):
  Royal Blue header band with Moss Green rule, white-edged seal + serif "City of / Fairfield" wordmark,
  "AI ASSISTANT · STAFF ONLY" label; new-chat screen: "HOW CAN WE HELP?" label between Moss rules, serif headline,
  no floating avatar, Draft / Summarize / Explain tiles (Cream / Light Moss / Blue Gray tint, dark text >= 7:1)
  under the message box that fill a starter prompt (never send) and are removed once a chat starts; squared
  controls; Royal Blue composer edge; serif caps sidebar headings; Royal Blue bar on the selected chat;
  Royal Blue tint on the user's own messages. Footer keeps "TSS" (user).
- [Mac] Mode picker (user: model picker "looks a bit misleading"): styled as "MODE <current> ▾" after a divider,
  no duplicate seal; search box visually hidden (kept for keyboard focus / screen readers); white focus ring
  on the band. librechat.yaml: interface.modelSelect false, which removes the raw "Fairfield AI ›" endpoint
  entry (its models skipped the specs' system prompts); spec labels/descriptions -> "General" ("Writing,
  summaries and City questions.") / "Images & screenshots" ("Reads images and screenshots you upload.").
  modelLabel unchanged, so the placeholder and reply name stay "Fairfield Assistant". Welcome text: 👋 removed.
- [Mac] Coordinated every shared-file edit and api recreate with the city-web session. The librechat.yaml lines
  above landed in that session's commit 78acac4; this commit has the branding files and the override's
  fairfield.js mount + script-tag lines.
- [Mac] Checked light, dark and phone width in the browser; tile fills the composer (React sees it), mode
  switching works, menu lists exactly the two specs, arrow keys still navigate it.
- Re-check after any LibreChat upgrade: fairfield.js keys off LibreChat markup (it fails quietly to stock UI).
