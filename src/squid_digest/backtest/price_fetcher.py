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
        
        # Get API key from parameter, env var, or use default test key
        self.coingecko_api_key = (
            coingecko_api_key or 
            os.getenv("COINGECKO_API_KEY") or 
            "CG-5pNpnHzumZtbhZmjQ6NXJmis"
        )
        
        self.client = httpx.Client(timeout=30.0)
        self._token_mapping: Optional[Dict[str, str]] = None
    
    def _load_token_mapping(self) -> Dict[str, str]:
        """Load token symbol to CoinGecko slug mapping from Leviathan API."""
        if self._token_mapping is not None:
            return self._token_mapping
        
        # Check cache first
        cache_file = self.cache_dir.parent / "token_mapping.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    self._token_mapping = json.load(f)
                    return self._token_mapping
            except Exception as e:
                print(f"Warning: Could not read token mapping cache: {e}")
        
        # Fetch from Leviathan API
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
                
                results = data.get("results", [])
                for token in results:
                    symbol = token.get("symbol", "").strip("$")
                    coingecko_slug = token.get("coingecko_slug")
                    
                    if symbol and coingecko_slug:
                        # Store uppercase version
                        symbol_upper = symbol.upper()
                        self._token_mapping[symbol_upper] = coingecko_slug
                        # Also store original case if different
                        if symbol != symbol_upper:
                            self._token_mapping[symbol] = coingecko_slug
                
                # Check if there are more pages
                if page >= total_pages:
                    break
                page += 1
                
                # Rate limiting
                time.sleep(0.1)
            
            # Cache the mapping
            try:
                with open(cache_file, 'w') as f:
                    json.dump(self._token_mapping, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not cache token mapping: {e}")
            
            print(f"Loaded {len(self._token_mapping)} token mappings")
            
        except Exception as e:
            print(f"Warning: Failed to fetch token mappings from Leviathan API: {e}")
            # Fall back to hardcoded mapping
            self._token_mapping = {
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
            }
            print("Using fallback token mapping")
        
        return self._token_mapping
    
    def get_coingecko_id(self, symbol: str) -> Optional[str]:
        """Get CoinGecko ID for a token symbol (case-insensitive)."""
        mapping = self._load_token_mapping()
        
        # Try exact match first
        if symbol in mapping:
            return mapping[symbol]
        
        # Try uppercase
        symbol_upper = symbol.upper()
        if symbol_upper in mapping:
            return mapping[symbol_upper]
        
        # Try without $ prefix
        symbol_no_dollar = symbol.strip("$")
        if symbol_no_dollar in mapping:
            return mapping[symbol_no_dollar]
        if symbol_no_dollar.upper() in mapping:
            return mapping[symbol_no_dollar.upper()]
        
        return None
    
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
                    # Convert keys from date strings to datetime for comparison
                    return cached
            except Exception as e:
                print(f"Warning: Could not read cache for {coingecko_id}: {e}")
        
        # Use market_chart endpoint for better efficiency
        # Calculate days between dates
        days = (end_date - start_date).days + 1
        
        prices = {}
        
        try:
            # Use market_chart endpoint which gives us daily data
            url = f"{self.BASE_URL}/coins/{coingecko_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': min(days, 90),  # Max 90 days for free tier
                'interval': 'daily'
            }
            
            # Add API key header if available
            headers = {}
            if self.coingecko_api_key:
                headers['x-cg-demo-api-key'] = self.coingecko_api_key
            
            response = self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Extract daily prices from the response
            if 'prices' in data:
                for price_point in data['prices']:
                    timestamp = price_point[0] / 1000  # Convert ms to seconds
                    price = price_point[1]
                    point_date = datetime.fromtimestamp(timestamp)
                    
                    # Only include dates in our range
                    if start_date <= point_date <= end_date:
                        date_key = point_date.strftime('%Y-%m-%d')
                        prices[date_key] = price
            
            # Rate limiting
            time.sleep(0.5)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"Warning: {coingecko_id} not found")
            else:
                print(f"Warning: HTTP error fetching {coingecko_id}: {e}")
        except Exception as e:
            print(f"Warning: Error fetching {coingecko_id}: {e}")
        
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
        
        # Fetch a small range around the date
        start_date = date - timedelta(days=1)
        end_date = date + timedelta(days=1)
        
        prices = self.fetch_price_history(coingecko_id, start_date, end_date)
        
        # Find the closest date (prices are keyed by YYYY-MM-DD)
        date_key = date.strftime('%Y-%m-%d')
        if date_key in prices:
            return prices[date_key]
        
        # Try previous day
        prev_date = date - timedelta(days=1)
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
