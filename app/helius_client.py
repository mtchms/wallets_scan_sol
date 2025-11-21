import logging
import httpx
from typing import Optional
import json

from app.models import TokenMetadata

logger = logging.getLogger(__name__)


class HeliusClient:
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.helius.xyz/v0"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_token_metadata(self, mint: str) -> Optional[TokenMetadata]:
        if not self.api_key:
            logger.warning("Helius API key не установлен")
            return None
        
        try:
            url = f"{self.base_url}/addresses/{mint}"
            params = {"api-key": self.api_key}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            metadata = TokenMetadata(
                mint=mint,
                name=data.get('name'),
                symbol=data.get('symbol'),
                uri=data.get('uri') or data.get('metadata', {}).get('uri'),
                creator=data.get('creator') or data.get('updateAuthority')
            )
            
            return metadata
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка при получении метадаты {mint}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения метадаты для {mint}: {e}")
            return None
    
    async def get_transaction_index(self, signature: str) -> Optional[int]:
        if not self.api_key:
            return None
        
        try:
            url = f"{self.base_url}/transactions"
            params = {
                "api-key": self.api_key,
                "transactions": [signature]
            }
            
            response = await self.client.post(url, json=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data and len(data) > 0:
                return data[0].get('index')
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения индекса транзакции {signature}: {e}")
            return None
    
    async def close(self):
        await self.client.aclose()