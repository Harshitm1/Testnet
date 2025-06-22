from delta_rest_client import DeltaRestClient, OrderType, TimeInForce
import logging
from config import DELTA_CONFIG

class DeltaExchange:
    def __init__(self, api_key=None, api_secret=None, base_url=None):
        self.api_key = api_key or DELTA_CONFIG['api_key']
        self.api_secret = api_secret or DELTA_CONFIG['api_secret']
        self.base_url = base_url or DELTA_CONFIG['base_url']
        
        # Initialize Delta REST client
        self.client = DeltaRestClient(
            base_url=self.base_url,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
        # Cache for product IDs and asset IDs
        self._product_ids = {}
        self._asset_ids = None
        
    def _get_product_id(self, symbol):
        """Get product ID for a symbol"""
        if symbol not in self._product_ids:
            # Get all products and find the matching one
            products = self.client.get_products()
            for product in products:
                if product['symbol'] == symbol:
                    self._product_ids[symbol] = product['id']
                    break
            if symbol not in self._product_ids:
                raise ValueError(f"Symbol {symbol} not found")
        return self._product_ids[symbol]

    def _get_asset_ids(self):
        """Get all asset IDs"""
        if self._asset_ids is None:
            try:
                assets = self.client.get_assets()
                self._asset_ids = [asset['id'] for asset in assets]
            except Exception as e:
                logging.error(f"Failed to get assets: {e}")
                raise
        return self._asset_ids

    def get_product_info(self, symbol):
        """Get product information"""
        product_id = self._get_product_id(symbol)
        return self.client.get_product(product_id)

    def place_order(self, symbol, side, size, order_type='market', price=None, reduce_only=False):
        """Place a new order"""
        try:
            product_id = self._get_product_id(symbol)
            
            order_params = {
                'product_id': product_id,
                'size': size,
                'side': side.lower(),
                'order_type': OrderType.MARKET if order_type == 'market' else OrderType.LIMIT,
                'time_in_force': TimeInForce.IOC if order_type == 'market' else TimeInForce.GTC
            }
            
            if price and order_type != 'market':
                order_params['limit_price'] = str(price)
            
            if reduce_only:
                order_params['reduce_only'] = True
                
            return self.client.place_order(**order_params)
            
        except Exception as e:
            logging.error(f"Failed to place order: {e}")
            raise

    def cancel_order(self, symbol, order_id):
        """Cancel an existing order"""
        try:
            product_id = self._get_product_id(symbol)
            return self.client.cancel_order(product_id, order_id)
        except Exception as e:
            logging.error(f"Failed to cancel order: {e}")
            raise

    def get_position(self, symbol):
        """Get current position for a symbol"""
        try:
            product_id = self._get_product_id(symbol)
            return self.client.get_position(product_id)
        except Exception as e:
            logging.error(f"Failed to get position: {e}")
            raise

    def get_wallet_balance(self):
        """Get wallet balance"""
        try:
            total_balance = 0
            # Get all asset IDs
            asset_ids = self._get_asset_ids()
            
            # Get balance for each asset
            for asset_id in asset_ids:
                try:
                    balance = self.client.get_balances(asset_id)
                    if balance and len(balance) > 0:
                        # Add available balance to total
                        total_balance += float(balance[0].get('available_balance', 0))
                except Exception as e:
                    logging.warning(f"Failed to get balance for asset {asset_id}: {e}")
                    continue
            
            return {'total_balance': total_balance}
            
        except Exception as e:
            logging.error(f"Failed to get wallet balance: {e}")
            raise

    def place_stop_loss(self, symbol, size, stop_price, side='sell'):
        """Place a stop-loss order"""
        try:
            product_id = self._get_product_id(symbol)
            
            return self.client.place_stop_order(
                product_id=product_id,
                size=size,
                side=side,
                order_type=OrderType.MARKET,
                stop_price=str(stop_price)
            )
            
        except Exception as e:
            logging.error(f"Failed to place stop loss: {e}")
            raise

    def modify_order(self, symbol, order_id, new_price=None, new_size=None):
        """Modify an existing order"""
        try:
            # Delta Exchange doesn't support direct order modification
            # So we'll cancel the old order and place a new one
            product_id = self._get_product_id(symbol)
            
            # Get the original order
            orders = self.client.get_live_orders()
            original_order = None
            for order in orders:
                if order['id'] == order_id:
                    original_order = order
                    break
                    
            if not original_order:
                raise ValueError(f"Order {order_id} not found")
                
            # Cancel the original order
            self.cancel_order(symbol, order_id)
            
            # Place new order with updated parameters
            return self.place_order(
                symbol=symbol,
                side=original_order['side'],
                size=new_size or original_order['size'],
                order_type='limit',
                price=new_price or original_order['limit_price']
            )
            
        except Exception as e:
            logging.error(f"Failed to modify order: {e}")
            raise

    def get_order_history(self, symbol=None):
        """Get order history"""
        try:
            query = {}
            if symbol:
                product_id = self._get_product_id(symbol)
                query['product_id'] = product_id
                
            response = self.client.order_history(query)
            return response.get('result', [])
            
        except Exception as e:
            logging.error(f"Failed to get order history: {e}")
            raise

    def get_trades(self, symbol=None):
        """Get recent trades"""
        try:
            query = {}
            if symbol:
                product_id = self._get_product_id(symbol)
                query['product_id'] = product_id
                
            response = self.client.fills(query)
            return response.get('result', [])
            
        except Exception as e:
            logging.error(f"Failed to get trades: {e}")
            raise 