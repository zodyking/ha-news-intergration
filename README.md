# Home Assistant News

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/zodyking/ai_news_anchor.svg)](https://github.com/zodyking/ai_news_anchor)
[![License](https://img.shields.io/github/license/zodyking/ai_news_anchor)](LICENSE)

A Home Assistant custom integration that generates and plays AI-written news briefings from Google News RSS feeds.

## Features

- 📰 Fetches headlines from Google News RSS feeds for 9 categories: U.S., World, Local, Business, Technology, Entertainment, Sports, Science, and Health
- 📊 Creates sensor entities for each news category with article data
- 🎨 Intuitive panel UI built with Shoelace components
- ⚙️ Fully configurable via Panel UI or Options Flow (no YAML editing required)
- 🔄 Automatic news fetching with configurable intervals
- 🔍 Supports custom query-based news sources

## Requirements

- Home Assistant 2023.1 or later
- One of the following AI services (optional, for future features):
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
           ├── strings.json
           ├── www/
           │   └── home_assistant_news/
           │       └── panel.html
           └── translations/
               └── en.json
   ```

2. Copy the `www/home_assistant_news/panel.html` file from the integration folder to your `config/www/home_assistant_news/` directory:
   ```
   config/
   └── www/
       └── home_assistant_news/
           └── panel.html
   ```

3. Restart Home Assistant

4. Go to **Settings** → **Devices & Services** → **Add Integration**

5. Search for "Home Assistant News" and add it

6. Configure the integration via **Panel UI** or **Options**:
   - **Local Geographic Area**: Your location for local news (e.g., "New York, NY")
   - **Max Articles Per Category**: 1-10 articles per category
   - **Scan Interval**: How often to fetch news (600-7200 seconds, default 1800)
   - **AI Mode**: Choose "auto", "google_generative_ai_conversation", or "conversation"
   - **Conversation Agent ID**: Required if AI mode is "conversation"
   - **Enabled Categories**: Toggle which categories to include
   - **Custom News Sources**: Add custom query-based news sources

## Usage

### Sensor Entities

The integration creates sensor entities for each news category:
- `sensor.home_assistant_news_u_s` - U.S. news
- `sensor.home_assistant_news_world` - World news
- `sensor.home_assistant_news_local` - Local news
- `sensor.home_assistant_news_business` - Business news
- `sensor.home_assistant_news_technology` - Technology news
- `sensor.home_assistant_news_entertainment` - Entertainment news
- `sensor.home_assistant_news_sports` - Sports news
- `sensor.home_assistant_news_science` - Science news
- `sensor.home_assistant_news_health` - Health news

Each sensor provides:
- **State**: Number of articles in that category
- **Attributes**: 
  - `Story 1 Title`, `Story 1 Article`, `Story 2 Title`, `Story 2 Article`, etc. (up to 10 stories)
  - Each story has a title and full article content scraped from the source

You can use these sensors in automations, templates, and dashboards to display news data.

### Panel UI

The integration includes an intuitive panel interface built with Shoelace web components. Access it by:

1. Clicking on "Home Assistant News" in the sidebar (if enabled)
2. Or navigating to `/home_assistant_news` in your browser

The panel allows you to:
- Configure all settings visually
- Manually refresh news data with the "Refresh News Data" button
- See real-time status and error messages
- Toggle news categories on/off
- Add and manage custom news sources

### Using Sensor Entities

You can use the sensor entities in automations and templates:

```yaml
# Example: Display news count in a template
{{ states('sensor.home_assistant_news_u_s') }} articles in U.S. news

# Example: Get first article title
{{ state_attr('sensor.home_assistant_news_world', 'Story 1 Title') if state_attr('sensor.home_assistant_news_world', 'Story 1 Title') else 'No articles' }}

# Example: Automation triggered by new articles
alias: Notify on New Technology News
trigger:
  - platform: state
    entity_id: sensor.home_assistant_news_technology
action:
  - service: notify.mobile_app
    data:
      message: "New tech news: {{ state_attr('sensor.home_assistant_news_technology', 'Story 1 Title') }}"
```

## How It Works

1. The integration fetches RSS feeds from Google News for enabled categories and custom sources
2. Articles are parsed and full article content is scraped from the source URLs
3. Article data is stored in sensor entities with attributes for each story
4. Sensors are updated automatically based on the configured scan interval
5. You can manually refresh data using the panel UI or by calling the refresh API endpoint

## Troubleshooting

- **No articles in sensors**: Check that at least one category is enabled and RSS feeds are accessible
- **Articles not loading**: The integration scrapes full article content from URLs. Some sites may block scraping. Check logs for errors.
- **Panel not showing**: Ensure the panel.html file is copied to `config/www/home_assistant_news/panel.html` and restart Home Assistant

## License

This integration is provided as-is for use with Home Assistant.

