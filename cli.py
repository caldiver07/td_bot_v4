import argparse
import sys
import json
import os

# Prevent the local './redis/' directory from shadowing the pypi 'redis' package
dir_path = os.path.dirname(os.path.realpath(__file__))
if sys.path[0] == '': 
    sys.path.pop(0)
if dir_path in sys.path: 
    sys.path.remove(dir_path)

from redis import Redis

def get_redis_client():
    try:
        client = Redis(host='localhost', port=6379, decode_responses=True, socket_connect_timeout=3)
        client.ping()
        return client
    except Exception as e:
        print(f"Error: Failed to connect to Redis.\n{e}")
        sys.exit(1)

def get_symbol(symbol):
    client = get_redis_client()
    symbol = symbol.upper()
    data = client.get(symbol)
    
    if data:
        try:
            parsed = json.loads(data)
            print(f"=== {symbol} ===")
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print(f"=== {symbol} (Raw String) ===")
            print(data)
    else:
        print(f"No data found in Redis for symbol: {symbol}")

def list_symbols():
    client = get_redis_client()
    keys = client.keys('*')
    if not keys:
        print("No keys found in Redis.")
        return
        
    print("=== Tracked Keys in Redis ===")
    for k in sorted(keys):
        print(f"- {k}")

def main():
    parser = argparse.ArgumentParser(description="TD Streamer CLI tool for testing data streams and Redis")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")
    
    # get command
    symbol_parser = subparsers.add_parser("get", help="Pull a specific symbol's real-time JSON payload from Redis")
    symbol_parser.add_argument("symbol", type=str, help="The ticker symbol to pull (e.g., AAPL)")
    
    # list command
    subparsers.add_parser("list", help="List all available symbols/keys currently stored in Redis")
    
    args = parser.parse_args()
    
    if args.command == "get":
        get_symbol(args.symbol)
    elif args.command == "list":
        list_symbols()

if __name__ == "__main__":
    main()
