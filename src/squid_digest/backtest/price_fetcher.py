"""Fetch historical price data from CoinGecko API."""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import httpx


class PriceFetcher:
    """Fetch historical price data from CoinGecko."""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    LEVIATHAN_TOKEN_URL = "https://api.leviathannews.xyz/api/v1/token/"
    
    def __init__(self, cache_dir: Optional[Path] = None, coingecko_api_key: Optional[str] = None):
        """Initialize price fetcher with optional cache directory and API key."""
        self.cache_dir = cache_dir or Path(".cache/prices")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Get API key from parameter or env var (required for rate limit avoidance)
        self.coingecko_api_key = (
            coingecko_api_key or 
            os.getenv("COINGECKO_API_KEY")
        )
        # Note: CoinGecko API key is optional but recommended to avoid rate limits
        # Set COINGECKO_API_KEY environment variable or pass as parameter
        
        self.client = httpx.Client(timeout=30.0)
        self._token_mapping: Optional[Dict[str, str]] = None
    
    def _load_token_mapping(self) -> Dict[str, str]:
        """Load token symbol to CoinGecko slug mapping from Leviathan API."""
        if self._token_mapping is not None:
            return self._token_mapping
        
        # Check cache first (but refresh if older than 1 day)
        cache_file = self.cache_dir.parent / "token_mapping.json"
        cache_valid = False
        if cache_file.exists():
            try:
                import os
                from datetime import datetime, timedelta
                cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                if cache_age < timedelta(days=1):
                    with open(cache_file, 'r') as f:
                        self._token_mapping = json.load(f)
                        print(f"Using cached token mapping ({len(self._token_mapping)} tokens)")
                        return self._token_mapping
            except Exception as e:
                print(f"Warning: Could not read token mapping cache: {e}")
        
        # Always fetch from Leviathan API (source of truth)
        print("Fetching token mappings from Leviathan API...")
        self._token_mapping = {}
        page = 1
        total_pages = None
        
        try:
            while True:
                response = self.client.get(
                    self.LEVIATHAN_TOKEN_URL,
                    params={"page": page},
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Get total pages on first request
                if total_pages is None:
                    total_pages = data.get("total_pages", 1)
                    print(f"Fetching {total_pages} pages of tokens...")
                
                results = data.get("results", [])
                for token in results:
                    symbol = token.get("symbol", "").strip("$")
                    coingecko_slug = token.get("coingecko_slug")
                    
                    # Only store tokens that have a CoinGecko slug
                    if symbol and coingecko_slug:
                        # Store uppercase version (primary)
                        symbol_upper = symbol.upper()
                        self._token_mapping[symbol_upper] = coingecko_slug
                        # Also store original case if different
                        if symbol != symbol_upper:
                            self._token_mapping[symbol] = coingecko_slug
                        # Store lowercase version too (for lookup)
                        symbol_lower = symbol.lower()
                        if symbol_lower != symbol_upper:
                            self._token_mapping[symbol_lower] = coingecko_slug
                
                # Check if there are more pages
                if page >= total_pages:
                    break
                page += 1
                
                # Small delay between pages
                time.sleep(0.1)
            
            # Merge fallback tokens for common tokens that might be missing
            # These are tokens that appear in signals but may not be in Leviathan API
            fallback_tokens = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'LINK': 'chainlink',
                'SOL': 'solana',
                'AAVE': 'aave',
                'UNI': 'uniswap',
                'CRV': 'curve-dao-token',
                'ENA': 'ethena',
                'BNB': 'binancecoin',
                'stETH': 'staked-ether',
                'USDT': 'tether',
                'USDC': 'usd-coin',
                'DAI': 'dai',
                'FRAX': 'frax',
                'XRP': 'xrp',
                'TRX': 'tron',
                'HYPE': 'hyperliquid',
                'YFI': 'yearn-finance',
                'POL': 'polygon-ecosystem-token',  # Polygon Ecosystem Token (formerly MATIC)
                'MATIC': 'matic-network',  # Legacy Polygon token name
                'NEAR': 'near',  # NEAR Protocol
                # Note: BASE - Base L2 doesn't have a token yet (as of 2025)
                # Note: FXUSD not found on CoinGecko - may need manual lookup or skip
            }
            # Add fallback tokens if not already in mapping (don't overwrite API data)
            for symbol, slug in fallback_tokens.items():
                if symbol.upper() not in self._token_mapping:
                    self._token_mapping[symbol.upper()] = slug
                if symbol not in self._token_mapping:
                    self._token_mapping[symbol] = slug
                if symbol.lower() not in self._token_mapping:
                    self._token_mapping[symbol.lower()] = slug
            
            # Cache the mapping
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_file, 'w') as f:
                    json.dump(self._token_mapping, f, indent=2)
                print(f"✓ Cached {len(self._token_mapping)} token mappings")
            except Exception as e:
                print(f"Warning: Could not cache token mapping: {e}")
            
            print(f"✓ Loaded {len(self._token_mapping)} token mappings from Leviathan API (with fallbacks)")
            
        except Exception as e:
            print(f"✗ ERROR: Failed to fetch token mappings from Leviathan API: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to hardcoded mapping - store in multiple cases for lookup
            fallback_tokens = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'LINK': 'chainlink',
                'SOL': 'solana',
                'AAVE': 'aave',
                'UNI': 'uniswap',
                'CRV': 'curve-dao-token',
                'ENA': 'ethena',
                'BNB': 'binancecoin',
                'stETH': 'staked-ether',
                'USDT': 'tether',
                'USDC': 'usd-coin',
                'DAI': 'dai',
                'FRAX': 'frax',
                'XRP': 'xrp',
                'TRX': 'tron',
                'HYPE': 'hyperliquid',
                'YFI': 'yearn-finance',
                'POL': 'polygon-ecosystem-token',  # Polygon Ecosystem Token (formerly MATIC)
                'MATIC': 'matic-network',  # Legacy Polygon token name
            }
            # Store in multiple cases for robust lookup
            self._token_mapping = {}
            for symbol, slug in fallback_tokens.items():
                self._token_mapping[symbol] = slug  # Original case
                self._token_mapping[symbol.upper()] = slug  # Uppercase
                self._token_mapping[symbol.lower()] = slug  # Lowercase
            print("⚠ Using fallback token mapping (Leviathan API unavailable)")
        
        return self._token_mapping
    
    def get_coingecko_id(self, symbol: str) -> Optional[str]:
        """Get CoinGecko ID for a token symbol (case-insensitive)."""
        mapping = self._load_token_mapping()
        
        # Normalize symbol (remove $ prefix)
        symbol_clean = symbol.strip("$")
        
        # Try exact match first (preserves original case)
        if symbol in mapping:
            coingecko_id = mapping[symbol]
        elif symbol_clean in mapping:
            coingecko_id = mapping[symbol_clean]
        # Try uppercase (most common)
        elif symbol_clean.upper() in mapping:
            coingecko_id = mapping[symbol_clean.upper()]
        # Try lowercase (for symbols that might come in lowercase)
        elif symbol_clean.lower() in mapping:
            coingecko_id = mapping[symbol_clean.lower()]
        # Try title case
        elif symbol_clean.capitalize() in mapping:
            coingecko_id = mapping[symbol_clean.capitalize()]
        else:
            return None
        
        # Fix known incorrect mappings from Leviathan API
        # CoinGecko uses "ripple" not "xrp"
        if coingecko_id == "xrp":
            coingecko_id = "ripple"
        
        return coingecko_id
    
    def fetch_price_history(
        self,
        coingecko_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, float]:
        """Fetch daily prices for a token using market_chart endpoint."""
        # Check cache first
        cache_file = self.cache_dir / f"{coingecko_id}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                    if cached:
                        print(f"Using cached prices for {coingecko_id} ({len(cached)} days)")
                        return cached
            except Exception as e:
                print(f"Warning: Could not read cache for {coingecko_id}: {e}")
        
        # Use market_chart endpoint for better efficiency
        # Calculate days between dates
        days = (end_date - start_date).days + 1
        
        # CoinGecko's market_chart endpoint returns the last N days from TODAY
        # We need to ensure we fetch enough days to include the start_date
        # Calculate days from start_date to today (not just to end_date)
        from datetime import datetime
        today = datetime.now().date()
        days_from_start = (today - start_date.date()).days + 1
        
        # For same-day or very recent dates, we need to fetch more days to get today's data
        # CoinGecko's market_chart endpoint returns data up to the current moment
        if days <= 1:
            # Fetch at least 7 days to ensure we get recent data
            days_to_fetch = max(7, days_from_start)
        else:
            # Fetch enough days to include start_date, but cap at 90 for free tier
            days_to_fetch = min(max(days, days_from_start), 90)
        
        prices = {}
        
        try:
            # Use market_chart endpoint which gives us daily data
            url = f"{self.BASE_URL}/coins/{coingecko_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days_to_fetch,
                'interval': 'daily'
            }
            
            # Add API key header if available
            headers = {}
            if self.coingecko_api_key:
                headers['x-cg-demo-api-key'] = self.coingecko_api_key
            
            print(f"Fetching prices for {coingecko_id} (last {days_to_fetch} days)...")
            response = self.client.get(url, params=params, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            # Extract daily prices from the response
            # Use the LATEST price point for each day (closing price, after news)
            # This ensures we're buying at prices AFTER the news broke, not before
            if 'prices' in data:
                # First pass: collect all price points with their timestamps
                price_points_by_date = {}  # date_key -> [(timestamp, price), ...]
                for price_point in data['prices']:
                    timestamp = price_point[0] / 1000  # Convert ms to seconds
                    price = price_point[1]
                    point_date = datetime.fromtimestamp(timestamp)
                    
                    # Only include dates in our range
                    if start_date.date() <= point_date.date() <= end_date.date():
                        date_key = point_date.strftime('%Y-%m-%d')
                        if date_key not in price_points_by_date:
                            price_points_by_date[date_key] = []
                        price_points_by_date[date_key].append((timestamp, price))
                
                # Second pass: use the latest timestamp for each date (closing price)
                for date_key, points in price_points_by_date.items():
                    # Sort by timestamp descending, take the first (latest)
                    points.sort(key=lambda x: x[0], reverse=True)
                    latest_timestamp, latest_price = points[0]
                    prices[date_key] = latest_price
                    
                    # Log timestamp for debugging (especially for today's date)
                    latest_time = datetime.fromtimestamp(latest_timestamp)
                    if date_key == datetime.now().strftime('%Y-%m-%d'):
                        print(f"  Today's price timestamp: {latest_time.strftime('%Y-%m-%d %H:%M:%S UTC')} (price: ${latest_price:.2f})")
                
                if prices:
                    print(f"✓ Fetched {len(prices)} price points for {coingecko_id}")
                else:
                    print(f"⚠ No prices in date range for {coingecko_id} (fetched {days_to_fetch} days)")
            else:
                print(f"⚠ No 'prices' key in response for {coingecko_id}")
            
            # Rate limiting
            time.sleep(0.5)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"✗ ERROR: CoinGecko ID '{coingecko_id}' not found (404)")
                print(f"  Verify the token exists on CoinGecko")
            else:
                print(f"✗ ERROR: HTTP {e.response.status_code} fetching {coingecko_id}: {e}")
                try:
                    error_body = e.response.text[:200]
                    print(f"  Response: {error_body}")
                except:
                    pass
        except httpx.TimeoutException:
            print(f"✗ ERROR: Timeout fetching prices for {coingecko_id}")
        except Exception as e:
            print(f"✗ ERROR: Exception fetching {coingecko_id}: {e}")
            import traceback
            traceback.print_exc()
        
        # If we need more than 90 days, fall back to individual date calls
        if days > 90:
            print(f"Warning: Date range >90 days, falling back to per-date fetching for {coingecko_id}")
            # Fall back to per-date fetching for remaining dates
            current_date = start_date
            while current_date <= end_date:
                date_key = current_date.strftime('%Y-%m-%d')
                if date_key not in prices:
                    date_str = current_date.strftime('%d-%m-%Y')
                    try:
                        url = f"{self.BASE_URL}/coins/{coingecko_id}/history"
                        params = {'date': date_str}
                        
                        # Add API key header if available
                        headers = {}
                        if self.coingecko_api_key:
                            headers['x-cg-demo-api-key'] = self.coingecko_api_key
                        
                        response = self.client.get(url, params=params, headers=headers)
                        response.raise_for_status()
                        data = response.json()
                        
                        if 'market_data' in data and 'current_price' in data['market_data']:
                            usd_price = data['market_data']['current_price'].get('usd')
                            if usd_price:
                                prices[date_key] = usd_price
                        
                        time.sleep(0.2)
                    except Exception as e:
                        print(f"Warning: Error fetching {coingecko_id} for {date_str}: {e}")
                
                current_date += timedelta(days=1)
        
        # Cache the results
        if prices:
            try:
                with open(cache_file, 'w') as f:
                    json.dump(prices, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not cache prices for {coingecko_id}: {e}")
        
        return prices
    
    def get_price(
        self,
        symbol: str,
        date: datetime,
        use_open: bool = True
    ) -> Optional[float]:
        """Get price for a token on a specific date."""
        coingecko_id = self.get_coingecko_id(symbol)
        if not coingecko_id:
            return None
        
        # For today or recent dates, fetch more days to ensure we get data
        # CoinGecko might not have today's data immediately
        days_back = 7 if date.date() >= (datetime.now().date() - timedelta(days=1)) else 3
        
        # Fetch a range around the date
        start_date = date - timedelta(days=days_back)
        end_date = date + timedelta(days=1)  # Include next day in case of timezone issues
        
        prices = self.fetch_price_history(coingecko_id, start_date, end_date)
        
        if not prices:
            return None
        
        # Find the closest date (prices are keyed by YYYY-MM-DD)
        date_key = date.strftime('%Y-%m-%d')
        if date_key in prices:
            return prices[date_key]
        
        # Try previous days (up to 7 days back)
        for days_back in range(1, 8):
            prev_date = date - timedelta(days=days_back)
            prev_key = prev_date.strftime('%Y-%m-%d')
            if prev_key in prices:
                return prices[prev_key]
        
        # Try next day
        next_date = date + timedelta(days=1)
        next_key = next_date.strftime('%Y-%m-%d')
        if next_key in prices:
            return prices[next_key]
        
        return None
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
