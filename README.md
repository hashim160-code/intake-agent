# ZScribe Intake Agent

AI-powered medical intake agent that makes outbound calls to collect patient information before appointments using dynamic templates from database.

## Features

- 🤖 **AI Agent**: Uses Google Gemini for natural conversations
- 📞 **Outbound Calls**: Makes calls via Telnyx SIP trunk
- 🎤 **Speech Processing**: Deepgram STT + Cartesia TTS
- 📋 **Dynamic Templates**: Database-driven intake questionnaires via API
- 🔄 **State Management**: Tracks conversation progress
- 🌐 **API Integration**: FastAPI server with Supabase database

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -e .
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start the API server:**
   ```bash
   python api_server.py
   ```

4. **Run the agent:**
   ```bash
   python src/calling_agent.py dev
   ```

5. **Make a test call:**
   ```bash
   python src/make_call.py
   ```

## Environment Variables

Required in `.env`:
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `SIP_OUTBOUND_TRUNK_ID`
- `GOOGLE_API_KEY`
- `DEEPGRAM_API_KEY`
- `CARTESIA_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

## Project Structure

```
├── api_server.py           # FastAPI server for templates
├── api_client.py           # API client for database access
├── src/
│   ├── calling_agent.py    # Main agent
│   ├── make_call.py        # Call initiation
│   ├── prompts.py          # Dynamic prompt generation
│   ├── tools.py            # Transcript tools
│   ├── state.py            # Conversation state
│   └── predefined_templates.py # Legacy templates (deprecated)
└── data/
    └── transcripts/        # Saved conversation transcripts
```

## API Endpoints

- `GET /templates/{template_id}` - Fetch template by ID
- `GET /health` - Health check
- `GET /debug/templates` - Debug all templates

## Templates

Templates are now stored in Supabase database and fetched dynamically via API. Each template contains:
- Template name and structure
- AI instructions
- Specific questions to ask
- Template type (intake/encounter)

## License

MIT
