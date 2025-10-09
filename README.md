# ZScribe Intake Agent

AI-powered medical intake agent that makes outbound calls to collect patient information before appointments.

## Features

- 🤖 **AI Agent**: Uses Google Gemini for natural conversations
- 📞 **Outbound Calls**: Makes calls via Telnyx SIP trunk
- 🎤 **Speech Processing**: Deepgram STT + Cartesia TTS
- 📝 **Transcripts**: Automatic conversation recording and saving
- 📋 **Templates**: Configurable intake questionnaires
- 🔄 **State Management**: Tracks conversation progress

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

3. **Run the agent:**
   ```bash
   python src/calling_agent.py dev
   ```

4. **Make a test call:**
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

## Project Structure

```
src/
├── calling_agent.py      # Main agent
├── make_call.py         # Call initiation
├── prompts.py           # Agent instructions
├── tools.py             # Transcript tools
├── state.py             # Conversation state
└── predefined_templates.py # Intake templates
```

## Templates

- **General Intake**: Standard medical questionnaire
- **Cardiology**: Heart-specific questions

## License

MIT
