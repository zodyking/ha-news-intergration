# Home Assistant News

A Home Assistant custom integration that generates and plays AI-written news briefings from Google News RSS feeds.

## Features

- 📰 Fetches headlines from Google News RSS feeds for 9 categories
- 📊 Creates sensor entities for each news category with article data
- 🎨 Intuitive panel UI built with Shoelace components
- ⚙️ Fully configurable via panel or options flow
- 🔄 Automatic news fetching with configurable intervals
- 🔍 Supports custom query-based news sources

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the three dots menu (⋮) → Custom repositories
4. Add this repository URL
5. Click "Home Assistant News" → Install
6. Restart Home Assistant
7. Go to Settings → Devices & Services → Add Integration
8. Search for "Home Assistant News" and add it

### Manual Installation

1. Copy the `home_assistant_news` folder to your `config/custom_components/` directory
2. Copy the `www/home_assistant_news/panel.html` file from the integration folder to your `config/www/home_assistant_news/` directory
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "Home Assistant News" and add it

## Requirements

- Home Assistant 2023.1 or later
- One of the following AI services (optional, for future features):
  - Google Generative AI Conversation integration, OR
  - A configured Conversation agent

## Configuration

After installation, configure the integration via:

1. **Panel UI** (Recommended): Navigate to `/home_assistant_news` in your browser or click "Home Assistant News" in the sidebar
2. **Options Flow**: Go to Settings → Devices & Services → Home Assistant News → Configure

### Settings

- **Local Geographic Area**: Your location for local news (e.g., "New York, NY")
- **Max Articles Per Category**: 1-10 articles per category
- **Scan Interval**: How often to fetch news (600-7200 seconds, default 1800)
- **AI Mode**: Choose "auto", "google_generative_ai_conversation", or "conversation"
- **Conversation Agent ID**: Required if AI mode is "conversation"
- **Enabled Categories**: Toggle which categories to include
- **Custom News Sources**: Add custom query-based news sources

## Usage

### Panel UI

Access the intuitive panel interface by clicking "Home Assistant News" in the sidebar or navigating to `/home_assistant_news`. The panel allows you to:
- Configure all settings visually
- Manually refresh news data with the "Refresh News Data" button
- See real-time status and error messages
- Toggle news categories on/off
- Add and manage custom news sources

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


