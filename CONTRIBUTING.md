# Contributing to Retail Sales Agent

Thank you for considering contributing to the Retail Sales Agent project! This guide will help you get started.

## Development Setup

### Prerequisites
- Python 3.11+
- Google Gemini API key
- Firebase project with Firestore enabled
- Razorpay test credentials (optional)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/Vedag812/Modish-AI-Retail-Assistant.git
cd Modish-AI-Retail-Assistant

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Populate database (first time only)
python data/populate_firebase.py

# Run the application
python app.py
```

## Architecture

The system uses a **multi-agent architecture** with 6 specialized AI agents:

```
                    ┌─────────────────────┐
                    │   Main Sales Agent   │
                    │   (Orchestrator)     │
                    └──────────┬──────────┘
                               │
        ┌──────────┬───────────┼───────────┬──────────┐
        ▼          ▼           ▼           ▼          ▼
   ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │Recommend.│ │Inventory│ │Loyalty │ │Payment │ │Fulfill.│
   │  Agent   │ │  Agent  │ │ Agent  │ │ Agent  │ │ Agent  │
   └─────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

### Adding a New Agent

1. Create agent file in `agents/worker_agents/`
2. Add tool functions in `utils/tools/`
3. Register the agent in `agents/sales_agent/sales_agent.py`
4. Update the routing logic in the orchestrator

## Code Style

- Follow PEP 8 conventions
- Add docstrings to all public functions
- Use type hints where possible
- Write meaningful commit messages

## Testing

```bash
# Run end-to-end tests
python test_e2e_flow.py

# Run payment flow tests
python test_payment_flow.py

# Verify database state
python check_orders.py
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes with clear messages
4. Push to your fork and open a PR
5. Ensure all tests pass before requesting review
