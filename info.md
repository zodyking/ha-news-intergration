# AI News Anchor

A Home Assistant custom integration that generates and plays AI-written news briefings from Google News RSS feeds.

## Features

- 📰 Fetches headlines from Google News RSS feeds for 9 categories
- 🤖 Uses Home Assistant's AI services to generate broadcast-style scripts
- 🔊 Plays briefings on media players using TTS
- 🎨 Intuitive panel UI built with Shoelace components
- ⚙️ Fully configurable via panel or options flow
- 🔄 Automatic news fetching with configurable intervals

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the three dots menu (⋮) → Custom repositories
4. Add this repository URL
5. Click "AI News Anchor" → Install
6. Restart Home Assistant
7. Go to Settings → Devices & Services → Add Integration
8. Search for "AI News Anchor" and add it

### Manual Installation

1. Copy the `ai_news_anchor` folder to your `config/custom_components/` directory
2. Copy the `www/ai_news_anchor/panel.html` file to your `config/www/ai_news_anchor/` directory
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "AI News Anchor" and add it

## Requirements

- Home Assistant 2023.1 or later
- A TTS integration configured (e.g., Google Cloud TTS, Amazon Polly, etc.)
- At least one media player entity
- One of the following AI services:
  - Google Generative AI Conversation integration, OR
  - A configured Conversation agent

## Configuration

After installation, configure the integration via:

1. **Panel UI** (Recommended): Navigate to `/ai_news_anchor` in your browser or click "AI News Anchor" in the sidebar
2. **Options Flow**: Go to Settings → Devices & Services → AI News Anchor → Configure

### Settings

- **Local Geographic Area**: Your location for local news (e.g., "New York, NY")
- **Max Articles Per Category**: 1-3 articles per category
- **Scan Interval**: How often to fetch news (600-7200 seconds, default 1800)
- **TTS Entity**: Select your TTS entity
- **Media Players**: Select one or more media players
- **AI Mode**: Choose "auto", "google_generative_ai_conversation", or "conversation"
- **Conversation Agent ID**: Required if AI mode is "conversation"
- **Pre-roll Delay**: Delay in milliseconds before speaking (0-300)
- **Enabled Categories**: Toggle which categories to include

## Usage

### Panel UI

Access the intuitive panel interface by clicking "AI News Anchor" in the sidebar or navigating to `/ai_news_anchor`. The panel allows you to:
- Configure all settings visually
- Test briefings with the "Play Briefing Now" button
- See real-time status and error messages
- Toggle news categories on/off

### Service Call

```yaml
service: ai_news_anchor.play_briefing
```

### Automation Example

```yaml
alias: Morning News Briefing
trigger:
  - platform: time
    at: "07:30:00"
action:
  - service: ai_news_anchor.play_briefing
mode: single
```

## News Categories

- U.S.
- World
- Local
- Business
- Technology
- Entertainment
- Sports
- Science
- Health

## Support

For issues, feature requests, or questions, please open an issue on GitHub.

## License

This integration is provided as-is for use with Home Assistant.


