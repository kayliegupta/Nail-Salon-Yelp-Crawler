# Nail Salon Yelp Crawler & AI Outreach Agent

An automated lead generation tool designed to help freelance web developers find potential clients. This agent crawls Yelp for nail salons in the San Francisco Bay Area that currently lack a website, generates personalized AI outreach messages using GPT-4o-mini, and compiles them into a beautiful HTML report.
Demo (2 min):  
👉 [https://loom.com/your-link](https://www.loom.com/share/0c5e806e87884d40bbb95eef43a54d67)

## Features

- **Smart City Rotation:** Automatically iterates through a list of Bay Area cities.
- **Deduplication:** Remembers previously discovered salons to ensure you never process the same lead twice.
- **Website Verification:** Performs a deep check to confirm the business doesn't already have a site listed.
- **AI Outreach:** Uses OpenAI to write warm, personalized messages referencing the salon's name, city, and Yelp rating.
- **Dual Output:** Generates a professional HTML Lead Report and appends to a master CSV database.

## 🛠 Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/kayliegupta/Nail-Salon-Yelp-Crawler.git
   cd Nail-Salon-Yelp-Crawler
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file in the root directory and add your API keys:
   ```env
   YELP_API_KEY=your_yelp_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```
   *   Get a Yelp API Key: Yelp Developers
   *   Get an OpenAI API Key: OpenAI Platform

## 📈 Usage

Simply run the main script:
```bash
python nail_salon_agent.py
```

The agent will fetch up to 10 new leads per run. You can adjust `MAX_LEADS` in the script configuration if needed.

## 📁 Output

- **`nail_salon_leads.html`**: A stylized, visual report for easy review.
- **`nail_salon_leads.csv`**: A master list of all leads found across all runs.
- **`.seen_salons.json`**: Persistence file to track deduplication (hidden).

## ⚖️ License

MIT License. Free to use and modify for your own outreach efforts.
