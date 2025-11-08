# Home Assistant News

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/zodyking/ai_news_anchor.svg)](https://github.com/zodyking/ai_news_anchor)
[![License](https://img.shields.io/github/license/zodyking/ai_news_anchor)](LICENSE)

A Home Assistant custom integration that generates and plays AI-written news briefings from Google News RSS feeds.

## Features

- 📰 Fetches headlines from Google News RSS feeds for 9 categories: U.S., World, Local, Business, Technology, Entertainment, Sports, Science, and Health
- 🤖 Uses Home Assistant's AI services (Google Generative AI or Conversation agents) to generate broadcast-style scripts
- 🔊 Plays briefings on one or more media players using TTS
- 🎨 Intuitive panel UI built with Shoelace components
- ⚙️ Fully configurable via Panel UI or Options Flow (no YAML editing required)
- 🔄 Automatic news fetching with configurable intervals
- 🎯 Exposes a service `home_assistant_news.play_briefing` for automation

## Requirements

- Home Assistant 2023.1 or later
- A TTS integration configured (e.g., Google Cloud TTS, Amazon Polly, etc.)
- At least one media player entity
- One of the following AI services:
  - Google Generative AI Conversation integration, OR
  - A configured Conversation agent

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three dots menu (⋮) → **Custom repositories**
4. Add this repository URL: `https://github.com/zodyking/ai_news_anchor`
5. Click **"Home Assistant News"** → **Install**
6. Restart Home Assistant
7. Go to **Settings** → **Devices & Services** → **Add Integration**
8. Search for "Home Assistant News" and add it

### Manual Installation

1. Copy the `home_assistant_news` folder to your `config/custom_components/` directory:
   ```
   config/
   └── custom_components/
       └── home_assistant_news/
           ├── __init__.py
           ├── manifest.json
           ├── const.py
           ├── config_flow.py
           ├── coordinator.py
           ├── summarizer.py
           ├── diagnostics.py
           ├── services.yaml
           ├── strings.json
           └── translations/
               └── en.json
   ```

2. Copy the `www/home_assistant_news/panel.html` file to your `config/www/home_assistant_news/` directory

3. Restart Home Assistant

4. Go to **Settings** → **Devices & Services** → **Add Integration**

5. Search for "Home Assistant News" and add it

6. Configure the integration via **Panel UI** or **Options**:
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

The integration includes an intuitive panel interface built with Shoelace web components. Access it by:

1. Clicking on "Home Assistant News" in the sidebar (if enabled)
2. Or navigating to `/home_assistant_news` in your browser

The panel allows you to:
- Configure all settings visually
- Test briefings with the "Play Briefing Now" button
- See real-time status and error messages
- Toggle news categories on/off
- Select TTS entities and media players from dropdowns

### Service Call

Call the service directly:

```yaml
service: home_assistant_news.play_briefing
```

With optional overrides:

```yaml
service: home_assistant_news.play_briefing
data:
  override_max_per_category: 1
  override_media_players:
    - media_player.living_room
  override_preroll_ms: 200
```

### Automation Example

```yaml
alias: Morning News Briefing
trigger:
  - platform: time
    at: "07:30:00"
action:
  - service: home_assistant_news.play_briefing
mode: single
```

### Multiple Times Per Day

```yaml
alias: Daily News Briefings
trigger:
  - platform: time
    at: "07:30:00"
  - platform: time
    at: "12:00:00"
  - platform: time
    at: "18:00:00"
action:
  - service: home_assistant_news.play_briefing
mode: single
```

## How It Works

1. The integration fetches RSS feeds from Google News for enabled categories
2. Articles are parsed and cleaned (HTML removed, whitespace collapsed)
3. A JSON payload is built with article titles and summaries
4. An AI prompt is constructed with strict formatting rules
5. The AI service generates a broadcast-style script
6. The script is spoken on configured media players using TTS

## Script Format

The generated script follows this format:

- Greeting: "Good morning," / "Good afternoon," / "Good night," (based on local time)
- For each category: "in the world of <Category>,"
- For each article: A 5-12 word title-style summary, followed by a concise paragraph
- Between articles: "Next up,"
- No links, markdown, or source attributions

## Troubleshooting

- **No items to brief**: Check that at least one category is enabled and RSS feeds are accessible
- **AI service error**: Ensure Google Generative AI Conversation is set up, or configure a Conversation agent
- **TTS errors**: Verify your TTS entity is configured correctly
- **Media player errors**: Check that media player entities exist and are available

## License

This integration is provided as-is for use with Home Assistant.

