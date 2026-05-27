# Solopreneur Agent Install Guide

這份文件是本機 hackathon demo 的完整安裝與重建流程。目標是跑起：

- Odoo 19 + `deal_to_delivery_agent` addon
- NemoClaw / OpenClaw sandbox
- Solopreneur OpenClaw plugin
- Agent App tool gateway
- Telegram ops bot

以下命令都從 repo root 執行：

```bash
cd /path/to/solopreneur-agent
```

## 1. Prerequisites

確認本機已有：

- Docker Desktop
- `uv`
- `git`
- `curl`
- NemoClaw CLI (`nemoclaw`)

快速檢查：

```bash
docker --version
uv --version
nemoclaw --version
```

如果 NemoClaw 尚未安裝，依官方 installer 或本 repo script 安裝：

```bash
bash scripts/setup_nemoclaw.sh
```

## 2. Environment

建立本機 `.env`：

```bash
cp .env.example .env
```

填入至少這些值：

```bash
NVIDIA_API_KEY=...
NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NIM_MODEL=nvidia/nemotron-3-super-120b-a12b
NIM_VISION_MODEL=<vision-capable-nvidia-model>

ODOO_URL=http://localhost:8069
ODOO_DATABASE=odoo
ODOO_USERNAME=<your-odoo-login-email>
ODOO_API_KEY=...

LINEAR_API_KEY=...
LINEAR_TEAM_ID=...

GITHUB_TOKEN=...
GITHUB_REPOSITORY=owner/repository

AGENT_TELEGRAM_BOT_TOKEN=...
AGENT_TELEGRAM_CHAT_ID=...
AGENT_TELEGRAM_ALLOWED_USER_IDS=...

SANDBOX=deal-demo
LIVE_WORKFLOW_ENABLED=0
```

注意：

- `.env` 不要 commit。
- `AGENT_TELEGRAM_CHAT_ID` 可以是你的 Telegram user id。
- `AGENT_TELEGRAM_ALLOWED_USER_IDS` 也填你的 Telegram user id，限制只有你能操作 live bot。
- `LIVE_WORKFLOW_ENABLED=0` 是安全預設。要真的打 Odoo / Linear / GitHub / Telegram 時才改成 `1` 或在命令前暫時加上。
- `NIM_VISION_MODEL` 是名片照片辨識用的 NVIDIA vision-capable model；只跑文字 deal workflow 時不會用到。
- 目前 delivery tracking 預設仍使用 Linear + GitHub。Odoo Project module 可以保留作為後續替代方向。

## 3. Python App

安裝 Python dependencies 並跑測試：

```bash
cd agent_app
uv sync
uv run pytest -q
cd ..
```

也可以從 repo root 跑：

```bash
make test
```

預期結果應該是所有非 live tests passing，live tests skipped。

## 4. Odoo

啟動 Odoo 19 和 Postgres：

```bash
make odoo-up
```

打開：

```text
http://localhost:8069
```

第一次啟動如果還沒有 database，先建立 database。建議：

- Database: `odoo`
- Email / login: 你的 Odoo login email
- Password: 自己設定並保存

登入後到 Apps 搜尋並安裝：

```text
Deal-to-Delivery Agent Bridge
```

安裝完成後確認上方有：

- `Deal Agent`
- `Deal Contexts`
- `Audit Logs`

live Odoo artifacts 會建立或更新：

- Contact / customer: `res.partner`
- CRM opportunity: `crm.lead`
- Quotation draft: `sale.order`
- Draft customer invoice: `account.move`
- Deal trace: `deal.agent.deal.context`
- Audit trace: `deal.agent.audit.log`

如果 addon 已安裝，但後續更新了 addon model / data / security CSV，執行 upgrade：

```bash
docker compose -f docker-compose.yml exec odoo bash -lc 'odoo -d odoo -u deal_to_delivery_agent --stop-after-init --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"'
```

## 5. Clean Rebuild Existing NemoClaw Sandbox

如果你之前用 custom image 建過 `deal-demo`，建議先清掉再用同名重建。

如果只是要強制用目前 repo 的 Dockerfile 乾淨重建同名 sandbox，優先用：

```bash
make nemoclaw-solopreneur-sandbox-recreate
```

這會呼叫 `nemoclaw onboard --fresh --recreate-sandbox`，避免 failed onboarding resume 復用舊的 `/sandbox/.openclaw/openclaw.json`。

如果 gateway state 也壞掉，再用下面的 destroy 路徑。

先停止 dashboard forward：

```bash
make nemoclaw-dashboard-stop
```

刪除舊 sandbox 和 gateway state：

```bash
make nemoclaw-solopreneur-sandbox-destroy-clean
```

如果你還有其他 sandbox 依賴同一個 gateway，改用：

```bash
make nemoclaw-solopreneur-sandbox-destroy
```

## 6. Create NemoClaw Sandbox

使用 custom NemoClaw sandbox image，並在 image build 時 bake 進本 repo 的 solopreneur OpenClaw plugin：

```bash
SANDBOX=deal-demo make nemoclaw-solopreneur-sandbox
```

這是目前官方支援的 OpenClaw plugin 安裝方式：plugin 是 OpenClaw runtime code package；skill 只是 `SKILL.md` 工作流說明；policy preset 只是網路 egress 規則。不要用 `nemoclaw sandbox skill install` 安裝 OpenClaw plugin。

`USE_CUSTOM_IMAGE=0` 只保留作為本機 debug fallback。它會先用預設 image 建 sandbox，再把 plugin copy 到 sandbox state；這條路線容易讓 dashboard tool catalog 和 gateway runtime 不同步，不建議 demo 用。

Onboarding 遇到選項時：

### Inference Provider

選：

```text
1) NVIDIA Endpoints
```

模型使用：

```text
nvidia/nemotron-3-super-120b-a12b
```

如果要求 API key，貼 NVIDIA API key。

### Messaging Channels

如果要用 OpenClaw Telegram channel，選 Telegram。若只要先測 dashboard，可以先略過或保留預設。

如果出現 group mention-only 類似問題：

- group demo：建議選 mention-only。
- private DM demo：這個設定不影響直接私訊。

### Policy Tier

選預設：

```text
Balanced
```

理由是後面會另外套本 repo 的 Odoo / Linear / tool gateway presets。`Restricted` 太容易卡 demo，`Open` 安全敘事較弱。

## 7. Apply Policies And Skill

套用本 repo 的 NemoClaw policies：

```bash
make nemoclaw-policies
```

安裝 deal-to-delivery skill：

```bash
make nemoclaw-skills
```

同步 OpenClaw workspace context：

```bash
make nemoclaw-workspace
```

如果 sandbox 是用 `USE_CUSTOM_IMAGE=0` 建的，或 dashboard 裡沒有看到 `solopreneur-tools` tools，重新安裝並刷新 plugin：

```bash
make nemoclaw-solopreneur-plugin-install
```

確認 sandbox 狀態：

```bash
nemoclaw deal-demo status
```

預期至少看到：

- Provider: NVIDIA / `nvidia-prod`
- Inference: healthy
- Agent: OpenClaw

在 dashboard 的 Agent / Tools 頁面應該看到 `solopreneur-tools`，包含：

- `crm_lookup`
- `business_card_capture`
- `deal_prepare`
- `odoo_upsert_contact`
- `odoo_create_crm_lead`
- `odoo_create_sale_order`
- `odoo_create_draft_invoice`
- `odoo_create_deal_artifacts`
- `delivery_create_tasks`
- `notify_stakeholder`

## 8. Dashboard

啟動 dashboard port forward：

```bash
make nemoclaw-dashboard-restart
```

這個 terminal 要保持開著。

另開一個 terminal 取得 tokenized URL：

```bash
nemoclaw deal-demo dashboard-url
```

打開 dashboard 後先用 New session 測模型：

```text
Reply with OK only.
```

預期 assistant 回：

```text
OK
```

如果卡住，讀 logs：

```bash
nemoclaw deal-demo exec -- openclaw logs --limit 200 --plain --timeout 5000
```

## 9. Tool Gateway

另開 terminal，啟動 host-side tool gateway：

```bash
make tool-gateway
```

如果你剛更新過 `agent_app/` 程式碼，先停止舊 gateway，再重啟，OpenClaw 才會吃到新的 connector/tool 行為。

健康檢查：

```bash
curl -sS http://localhost:8088/health
```

也可以從 sandbox 檢查：

```bash
nemoclaw deal-demo exec -- curl -sS http://host.openshell.internal:8088/health
```

## 10. OpenClaw Dry Run Test

在 OpenClaw dashboard 貼：

```text
Use the deal-to-delivery skill.

我剛收到 Acme Studio 的需求：他們要一個兩週的 Odoo CRM automation package，下週一開始，預算 USD 8000。範圍包含 lead capture、quote generation、delivery task tracking，以及 delivery ready 時通知 stakeholder。聯絡人是 Ada Lovelace，ada@example.com。

先幫我準備 deal brief，判斷需要建立哪些外部紀錄；如果需要 live side effects，先列出將會動到的系統和安全限制，不要 finalize invoice，不要 mark won。
```

預期：

- 會產生 deal brief / assumptions / planned actions。
- 不應 finalize invoice。
- 不應 mark deal won。
- 應提到 Odoo / Linear / GitHub / Telegram refs 或下一步。

## 11. Full-Live Workflow

只有在 Odoo、Linear、GitHub、Telegram env 都完成後才開 live。

啟動 gateway 時改用：

```bash
LIVE_WORKFLOW_ENABLED=1 make tool-gateway
```

在 OpenClaw 內執行 live workflow 前，確認它會遵守：

- invoice 只能 draft
- 不 mark deal won
- 所有外部 side effects 要有 audit / refs
- Telegram 只發給允許的 operator / chat

建議先測 Odoo live artifacts，不急著打 Linear / GitHub / Telegram：

```text
我批准 live mode。請為 Acme Studio 建立 Odoo draft deal artifacts，但不要 mark won，也不要 finalize invoice。

客戶需求：Acme Studio 要一個兩週的 Odoo CRM automation package，下週一開始，預算 USD 8000。範圍包含 lead capture、quote generation、delivery task tracking，以及 delivery ready 時通知 stakeholder。聯絡人 Ada Lovelace，ada@example.com。
```

預期工具順序：

1. `deal_prepare` with `live=true`
2. `odoo_upsert_contact` with `live=true`
3. `odoo_create_crm_lead` with `live=true`
4. `odoo_create_sale_order` with `live=true`
5. `odoo_create_draft_invoice` with `live=true`

預期 Odoo UI 可看到：

- Contact: Ada Lovelace / Acme Studio
- CRM opportunity
- Sales quotation draft
- Draft invoice
- Deal Agent context and audit log

`odoo_create_deal_artifacts` 可以作為一鍵 fallback，但 judge-facing demo 優先用 atomic tools，讓評審看見 agent 自己按需求拆步驟。

## 12. Telegram Ops Bot

啟動第二支 bot，用於 solopreneur daily-life demo：

```bash
make telegram-ops
```

測試：

```text
/start
```

CRM lookup：

```text
查 Acme 聯絡方式
```

Business card flow：

- 傳一張名片照片給 bot。
- 預期 bot 會抽取聯絡人資訊。
- live mode 下會建立或更新 Odoo contact / CRM lead。

## 13. Common Issues

### Dashboard port already in use

```bash
make nemoclaw-dashboard-stop
make nemoclaw-dashboard
```

或換 port：

```bash
LOCAL_DASHBOARD_PORT=18790 make nemoclaw-dashboard
```

### OpenClaw shows OpenAI API key error

通常是 dashboard session 選到 OpenAI model。重開 New session，選 NVIDIA model：

```text
nvidia/nemotron-3-super-120b-a12b
```

### Unknown model: nvidia/nvidia/...

通常是 dashboard session 裡 provider/model override 疊到了。建立 New session，使用 default 或正確的 NVIDIA model，不要手動選出 double-prefix 的值。

### LLM request failed: network connection error

先確認 sandbox 是用目前 repo 的 custom image 重建，而不是舊的 default-image fallback：

```bash
nemoclaw deal-demo status
```

正常 demo 不要設定 `USE_CUSTOM_IMAGE=0`。如果你剛改過 plugin 或 Dockerfile，先 destroy 舊 sandbox 再重建。

再確認：

```bash
nemoclaw deal-demo exec -- openclaw logs --limit 200 --plain --timeout 5000
```

### Telegram polling already active

同一支 OpenClaw Telegram bot token 已有 poller 在跑。先停止舊 sandbox / 舊 gateway，或使用另一支 bot token。

### Tool gateway missing config

full workflow 在 `LIVE_WORKFLOW_ENABLED=1` 時會要求所有 live integrations env 都存在。先檢查 `.env` 是否有：

```bash
NVIDIA_API_KEY
ODOO_API_KEY
LINEAR_API_KEY
LINEAR_TEAM_ID
GITHUB_TOKEN
GITHUB_REPOSITORY
AGENT_TELEGRAM_BOT_TOKEN
AGENT_TELEGRAM_CHAT_ID
```

只測 Odoo atomic tools 時，至少需要：

```bash
NVIDIA_API_KEY
ODOO_API_KEY
```

## 14. Recommended Demo Order

1. Odoo UI：展示 addon 已安裝、Deal Contexts / Audit Logs。
2. OpenClaw dashboard：`Reply with OK only.`。
3. OpenClaw dry-run customer request。
4. Tool gateway full-live run。
5. Odoo CRM / Sales / Draft Invoice / Deal Contexts / Audit Logs。
6. Linear tasks。
7. GitHub tracking issue。
8. Telegram stakeholder update。
9. Telegram ops bot：查 CRM 聯絡方式、名片拍照入 CRM。
