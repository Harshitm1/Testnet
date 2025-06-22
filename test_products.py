from delta_rest_client import DeltaRestClient
import requests
from config import DELTA_CONFIG

# Initialize client
client = DeltaRestClient(
    base_url=DELTA_CONFIG['base_url'],
    api_key=DELTA_CONFIG['api_key'],
    api_secret=DELTA_CONFIG['api_secret']
)

# Get products directly from API
response = requests.get(f"{DELTA_CONFIG['base_url']}/v2/products")
data = response.json()

if 'result' in data:
    # Find ETH-related products
    print("\nETH Products:")
    for product in data['result']:
        if isinstance(product, dict) and 'symbol' in product and 'ETH' in product['symbol']:
            print(f"Symbol: {product['symbol']}")
            print(f"ID: {product['id']}")
            print(f"Description: {product.get('description', 'N/A')}")
            print(f"Type: {product.get('contract_type', 'N/A')}")
            print("---")
else:
    print("Error: Could not get products data")
    print("Response:", data) 