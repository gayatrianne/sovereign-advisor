# Sovereign Advisor 🏛️

> **Multi-Agent AI Financial Advisory System**  
> Built with Microsoft Copilot Studio · Azure AI Foundry · FastMCP · Python

A fully orchestrated, multi-agent AI system that conducts structured financial fact-finds, matches clients to suitable products via RAG, and generates personalised adviser briefings using GPT-4o — deployed in Microsoft Teams.

---

## 🏗️ Architecture

```
User (Teams)
    │
    ▼
Sovereign Advisor Orchestrator        ← Microsoft Copilot Studio
    │  • Conducts fact-find (one question at a time)
    │  • Presents summary confirmation
    │  • Holds client while processing
    │
    ├──► Product Matcher (Child Agent) ← Copilot Studio Child Agent
    │        • RAG over SharePoint KB
    │        • Returns matched products only
    │        • No user-facing output
    │
    └──► Sovereign-Suitability-Engine ← Azure AI Foundry (GPT-4o)
             • Receives: client data + matched products
             • Calls MCP tools for live calculations
             • Returns: structured adviser briefing
                 │
                 ▼
             sovereign-mcp (FastMCP Server)  ← Python / Local + ngrok
                 • 8 financial calculation tools
                 • Pydantic validation
                 • SSE / Streamable-HTTP transport
```

---

## ✨ Features

- **Conversational fact-find** — asks one question at a time, natural language, no form-filling
- **Summary confirmation** — presents collected data before processing, allows corrections
- **Hold message** — informs client that analysis is underway
- **RAG product matching** — retrieves relevant products from a SharePoint knowledge base
- **Live financial calculations** — 8 MCP tools called by the Foundry agent on demand
- **Structured adviser briefing** — GPT-4o generates a professional, citation-free briefing
- **Teams deployment** — live in Microsoft Teams channel

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | Microsoft Copilot Studio (Sovereign Advisor agent) |
| Child Agent | Microsoft Copilot Studio (Product Matcher) |
| Suitability Engine | Azure AI Foundry — GPT-4o (`Sovereign-Suitability-Engine`) |
| Knowledge Base | SharePoint (KB001–KB007 + Required-Fields-by-Persona) |
| Calculation Tools | FastMCP Python server (8 tools) |
| Tunnel | ngrok (SSE/Streamable-HTTP) |
| Deployment | Microsoft Teams channel |

---

## 📐 MCP Tools (Financial Calculations)

All 8 tools accept flat key-value parameters (Azure AI Foundry compatibility).

| Tool | Description |
|---|---|
| `debt_cost` | Monthly interest cost and total debt burden |
| `transfer_fee_vs_interest` | Balance transfer fee vs. interest saving comparison |
| `savings_gap` | Gap between current savings trajectory and target |
| `emergency_fund_target` | Recommended emergency fund size by persona |
| `pension_gap` | Projected pension shortfall at retirement |
| `drawdown_sustainability` | Years a pension pot will last in drawdown |
| `mortgage_affordability` | Maximum borrowing and monthly repayment estimate |
| `jisa_projection` | Junior ISA growth projection to age 18 |

---

## 📚 Knowledge Base

The KB documents are hosted in SharePoint and connected as a knowledge source in Copilot Studio. They are not included in this repository.

| File | Purpose |
|---|---|
| KB001–KB006 | Product knowledge base (ISAs, pensions, mortgages, etc.) |
| KB007 | Standard fact-find question set |
| Required-Fields-by-Persona | Minimum data fields by client life stage |

> To replicate the setup, create a SharePoint site, upload your own KB documents, and point the Copilot Studio knowledge source to that site.

---

## ⚙️ Setup & Running Locally

### Prerequisites

- Python 3.11+
- Azure AI Foundry project with an agent created
- Microsoft Copilot Studio environment
- ngrok account (free tier works)
- SharePoint site with knowledge base documents

### 1. Install dependencies

```bash
pip install fastmcp pydantic uvicorn
```

### 2. Start the MCP server

```bash
python main.py
```

The server starts on `http://0.0.0.0:8000`.  
All 8 tools are registered automatically on startup.

### 3. Start ngrok tunnel

```bash
ngrok http 8000
```

Copy the HTTPS forwarding URL (e.g. `https://your-subdomain.ngrok-free.dev`).

### 4. Configure Azure AI Foundry

1. Open your Foundry project → **Agents** → `Sovereign-Suitability-Engine`
2. Under **Tools → MCP**, set the server URL to:  
   `https://your-subdomain.ngrok-free.dev/sse`
3. Enable **Activity Protocol v2** (A2A) using the helper script:

```python
# enable_activity.py
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint="https://<your-foundry>.services.ai.azure.com/api/projects/proj-default",
    credential=DefaultAzureCredential()
)
agent = client.agents.update_agent(
    agent_id="<your-agent-id>",
    metadata={"protocols": ["activity+responses"]}
)
print(f"Status: 200  protocols: {agent.metadata.get('protocols')}")
```

### 5. Configure Copilot Studio

**Product Matcher (Child Agent):**
- Add SharePoint knowledge source pointing to your KB documents
- System prompt: Retrieve matching financial products based on client data. Return structured list only. Do not present output to the user.
- Add as child agent to Sovereign Advisor Orchestrator

**Sovereign Advisor (Orchestrator):**
- Add Product Matcher as **child agent**
- Add Sovereign-Suitability-Engine as **connected agent** (Activity Protocol v2)
- Set system prompt with fact-find instructions (see `orchestrator_system_prompt.txt`)

### 6. Deploy to Teams

Copilot Studio → **Channels** → **Microsoft Teams** → Publish

---

## 💬 Example Conversation Flow

```
Sovereign Advisor: Good morning! I'm Sovereign Advisor. What brings you in today?

User: I want to review my finances and retirement planning.

Sovereign Advisor: Great — let's start with the basics. What's your current age?

User: 42

Sovereign Advisor: And what's your approximate annual income?

User: Around £65,000

... [continues one question at a time] ...

Sovereign Advisor: Thank you. Here's a summary of what I've collected:
  • Age: 42 | Life stage: Mid-career
  • Income: £65,000 | Pension pot: £45,000
  • Mortgage: £280,000 remaining | Monthly contribution: £400
  Does everything look correct, or would you like to change anything?

User: That's all correct.

Sovereign Advisor: Perfect — I'm now running your personalised analysis. This will take a moment...

[Adviser Briefing returned]
```

---

## 🗂️ Repository Structure

```
sovereign-advisor/
├── main.py                        # FastMCP server entry point — registers all 8 tools
├── enable_activity.py             # One-time script to enable A2A on Foundry agent
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variable template
├── README.md
├── screenshots/                   # Project screenshots
│   └── *.png
└── src/
    ├── config.py                  # Configuration and environment loading
    ├── models/
    │   └── schemas.py             # Pydantic input/output models
    └── tools/
        ├── debt.py                # debt_cost, transfer_fee_vs_interest
        ├── investments.py         # jisa_projection
        ├── mortgage.py            # mortgage_affordability
        ├── pension.py             # pension_gap, drawdown_sustainability
        └── savings.py             # savings_gap, emergency_fund_target
```

> **Note:** The `kb/` folder is not included. KB documents (KB001–KB007 and Required-Fields-by-Persona) are hosted in SharePoint as the live knowledge source for Copilot Studio.

---

## 🔑 Key Technical Decisions

### Flat MCP parameters
Azure AI Foundry sends tool calls as flat key-value pairs, not nested objects. All 8 MCP tools accept flat parameters and construct Pydantic models internally:

```python
@mcp.tool()
def pension_gap(
    pot_gbp: float,           # Foundry sends: pot_gbp (not current_pot_gbp)
    years_to_retirement: int,
    ...
) -> dict:
    inp = PensionGapInput(
        current_pot_gbp=pot_gbp,  # mapped internally
        ...
    )
    return calculate_pension_gap(inp).model_dump()
```

### Two-hop vs three-hop architecture
An Orchestrator → Child → Connected Agent chain caused timeouts (>15 min). Restructured to:
- Child agent handles **KB RAG only** (fast, no LLM chain)
- Orchestrator calls Foundry **directly** as connected agent
- Eliminates one LLM hop and resolves timeout

### Structured handoff format
Copilot Studio wraps connected agent calls in natural language task descriptions. Using structured key-value text (not JSON) ensures reliable parsing by the Foundry agent:

```
Case reference: ADV-2024-001. Life stage: Mid-career. Age: 42.
Annual income: £65,000. Pension pot: £45,000. Monthly contribution: £400.
Matched products: Personal Pension, Stocks & Shares ISA.
```

---

## 👩‍💻 Author

**Gayatri Anne**  
AI & Cloud Architect | 18+ Years Enterprise IT  
[GitHub: gayatrianne/sovereign-advisor](https://github.com/gayatrianne/sovereign-advisor)

---

## 📄 Licence

MIT — free to use, adapt and build upon.
