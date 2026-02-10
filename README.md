# Price Tracker - Production Application

A full-stack NZ IT product price comparison tool. Search across PBTech, Noel Leeming, JB Hi-Fi, and Acquire simultaneously, then track prices over time.

## Setup

### Prerequisites

- Python 3.8+
- Node.js 18+

### Backend

```bash
# Install Python dependencies
pip install flask flask-cors playwright

# Install Chromium for Playwright
playwright install chromium

# Start the API
python api.py
```

The API runs at **http://localhost:5000**.

### Frontend

```bash
npm install
npm run dev
```

The frontend runs at **http://localhost:5173**.

## Project Structure

```
api.py                    # Flask REST API - search, add, delete, check prices
api_secure.py             # Enhanced API with rate limiting and security
database.py               # SQLite database with product groups schema
SECURITY.md               # Security guidelines
start_api.sh              # Production startup script
src/
  playwright_scraper.py   # Playwright-based scrapers for 4 NZ retailers
  PriceComparison.jsx     # Main React component - search, compare, track
  PriceTracker.jsx        # Alternative product tracker view
  App.jsx                 # React app entry point
  main.jsx                # Vite entry point
  index.css               # Tailwind CSS imports
  App.css                 # App-level styles
```

## Supported Retailers

| Retailer | Domain | Price Selector |
|----------|--------|---------------|
| PBTech | pbtech.co.nz | `.js-customer-price` |
| Noel Leeming | noelleeming.co.nz | `[data-price]` / `.price.sale` |
| JB Hi-Fi | jbhifi.co.nz | `[data-testid="ticket-price"]` |
| Acquire | acquire.co.nz | `.price-actual.tax1` |

## How It Works

### Search Flow

1. Enter a product name in the frontend
2. Backend searches all 4 retailers in parallel (ThreadPoolExecutor)
3. Each retailer's search function finds matching product URLs
4. Playwright scrapes each URL for price, name, model, and brand
5. Frontend deduplicates results by model number
6. Select a product to track across all retailers
7. Products are saved as a group for ongoing price comparison

### Database

SQLite with three tables:
- **product_groups** - Groups the same product across retailers (linked by model number)
- **products** - Individual listings with retailer, URL, price
- **price_history** - Historical price records for trend tracking

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/products` | List all tracked products |
| POST | `/api/search-preview` | Search retailers without saving |
| POST | `/api/products/add-selected` | Save selected products |
| DELETE | `/api/products/:id` | Delete a product |
| GET | `/api/groups` | List product groups |
| GET | `/api/groups/:id` | Price comparison for a group |
| DELETE | `/api/groups/:id` | Delete a group and its products |
| POST | `/api/check-prices` | Re-scrape all tracked products |
| GET | `/api/products/:id/history` | Price history (query: `days`) |

## Production Deployment

Use `api_secure.py` instead of `api.py` for production. It adds rate limiting and input validation.

```bash
# Option 1: Direct
python api_secure.py

# Option 2: Startup script
chmod +x start_api.sh
./start_api.sh

# Build frontend
npm run build
# Serve dist/ with any static file server
```

## Adding a New Retailer

1. Add `search_<retailer>()` and `scrape_<retailer>()` functions in `src/playwright_scraper.py`
2. Register both functions in `api.py`'s retailer lists
3. Add URL detection in the `check_prices` endpoint

See `IMPLEMENTATION_GUIDE.md` in the parent directory for detailed instructions.
