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
