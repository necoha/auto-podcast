# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI Auto Podcast system that uses Notebook LM's Audio Overview feature to automatically generate and distribute podcasts. The system collects content from RSS feeds, processes it through Notebook LM, and publishes episodes via RSS feed using GitHub Actions and GitHub Pages - all completely free.

## Technology Stack

- **Python 3.11+** - Main application language
- **Selenium** - Web automation for Notebook LM interaction
- **feedgen** - RSS feed generation
- **GitHub Actions** - CI/CD and scheduling
- **GitHub Pages** - Free hosting for audio files and RSS feeds

## Common Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your Google credentials

# Create required directories
mkdir -p audio_files content static
```

### Manual Podcast Generation
```bash
# Generate a single episode
python podcast_generator.py

# Generate RSS feed
python -c "from rss_feed_generator import RSSFeedGenerator; RSSFeedGenerator().generate_rss_feed()"

# Test content collection
python -c "from content_manager import ContentManager; ContentManager().create_daily_content(['AI', 'Technology'])"
```

### Testing Individual Components
```bash
# Test RSS feed collection
python content_manager.py

# Test RSS feed generation  
python rss_feed_generator.py

# Test Notebook LM automation (requires valid credentials)
python notebooklm_automation.py
```

## Architecture

### Core Components

1. **ContentManager** (`content_manager.py`)
   - Fetches articles from RSS feeds
   - Processes content for podcast format
   - Manages content files and metadata

2. **NotebookLMAutomator** (`notebooklm_automation.py`)
   - Selenium-based web automation
   - Handles Google login, notebook creation, content upload
   - Automates Audio Overview generation and download

3. **PodcastGenerator** (`podcast_generator.py`)
   - Main orchestration class
   - Integrates content collection and audio generation
   - Manages daily limits and scheduling

4. **RSSFeedGenerator** (`rss_feed_generator.py`)
   - Generates standard podcast RSS feeds
   - Includes iTunes-compatible metadata
   - Validates feed structure

### File Structure
```
audio_files/     - Generated MP3 episodes
content/         - Source content and metadata  
static/          - Deployed web files
.github/workflows/ - GitHub Actions automation
```

### Automation Flow

1. **GitHub Actions** triggers daily at 9 AM JST
2. **ContentManager** fetches latest articles from configured RSS feeds
3. **NotebookLMAutomator** creates Audio Overview via Selenium
4. **RSSFeedGenerator** updates podcast feed
5. **GitHub Pages** serves audio files and RSS feed

## Configuration

### Key Settings in `config.py`

- `MAX_DAILY_GENERATIONS = 3` - Notebook LM free tier limit
- `RSS_FEEDS` - List of news sources to monitor
- `GENERATION_SCHEDULE` - Frequency (daily/weekly/hourly)
- `MAX_CONTENT_LENGTH` - Character limit for input content

### Required Secrets (GitHub Actions)

- `GOOGLE_OAUTH_CREDENTIALS` - OAuth credentials from Google Cloud Console (Base64 encoded)
- `PODCAST_BASE_URL` - GitHub Pages URL for hosting
- `OAUTH_SESSION_DATA` - Pre-authenticated session data (optional, for CI/CD)

**Important**: Uses secure OAuth authentication. See OAUTH_SETUP.md for detailed setup instructions.

## Free Service Limits

- **Notebook LM**: 3 audio generations per day (free tier)
- **GitHub Actions**: 2000 minutes per month (free tier)  
- **GitHub Pages**: 1GB storage, 100GB bandwidth per month
- **File retention**: Audio files cleaned up after 30 days

## Development Notes

- Selenium requires Chrome/Chromium for Notebook LM automation
- GitHub Actions workflow includes Chrome installation
- RSS feeds must be publicly accessible
- Audio files are served directly from GitHub Pages
- Content length is limited to prevent Notebook LM timeouts

## Troubleshooting

- **Login issues**: Check 2FA settings, consider app passwords
- **Generation failures**: Verify daily limits not exceeded
- **Audio quality**: Adjust custom prompts for better Notebook LM output
- **Feed validation**: Use podcast validators before publishing