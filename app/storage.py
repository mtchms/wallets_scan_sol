import json
import os
import logging
import csv
from typing import List, Optional, Dict
from datetime import datetime
import aiofiles

from app.models import HeliusTransaction, ScamDetectionResult

logger = logging.getLogger(__name__)


class Storage:
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.transactions_dir = os.path.join(data_dir, "transactions")
        self.results_file = os.path.join(data_dir, "scam_results.json")
        self.csv_file = os.path.join(data_dir, "scam_results.csv")
        self.metadata_cache_file = os.path.join(data_dir, "token_metadata_cache.json")
        
        self._results_cache: Dict[str, ScamDetectionResult] = {}
    
    async def initialize(self):
        os.makedirs(self.transactions_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        if os.path.exists(self.results_file):
            try:
                async with aiofiles.open(self.results_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
                    self._results_cache = {
                        k: ScamDetectionResult(**v) for k, v in data.items()
                    }
                logger.info(f"Загружено {len(self._results_cache)} результатов из кеша")
            except Exception as e:
                logger.error(f"Ошибка загрузки результатов: {e}")
        
        logger.info("Storage инициализирован")
    
    async def add_transaction(self, mint: str, transaction: HeliusTransaction): # просто для хранения результатов в json
        mint_file = os.path.join(self.transactions_dir, f"{mint}.json")
        
        transactions = []
        if os.path.exists(mint_file):
            try:
                async with aiofiles.open(mint_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    transactions = json.loads(content)
            except Exception as e:
                logger.error(f"Ошибка чтения транзакций для {mint}: {e}")
        
        tx_dict = transaction.model_dump()
        if not any(t.get('signature') == tx_dict['signature'] for t in transactions):
            transactions.append(tx_dict)
            
            async with aiofiles.open(mint_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(transactions, indent=2, ensure_ascii=False))
    
    async def get_token_transactions(self, mint: str) -> List[HeliusTransaction]: # просто для хранения результатов в json
        mint_file = os.path.join(self.transactions_dir, f"{mint}.json")
        
        if not os.path.exists(mint_file):
            return []
        
        try:
            async with aiofiles.open(mint_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
                return [HeliusTransaction(**tx) for tx in data]
        except Exception as e:
            logger.error(f"Ошибка загрузки транзакций для {mint}: {e}")
            return []
    
    async def save_result(self, result: ScamDetectionResult): # просто для хранения результатов в json
        self._results_cache[result.mint] = result
        
        try:
            data = {k: v.model_dump() for k, v in self._results_cache.items()}
            async with aiofiles.open(self.results_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Ошибка сохранения результата: {e}")
    
    async def get_result(self, mint: str) -> Optional[ScamDetectionResult]:
        return self._results_cache.get(mint)
    
    async def get_all_results(self) -> List[ScamDetectionResult]:
        return list(self._results_cache.values())
    
    async def export_to_csv(self) -> str:
        results = await self.get_all_results()
        
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['mint', 'status', 'reasons'])
            
            for result in results:
                status = 'scam' if result.is_scam else 'not_scam'
                reasons = '; '.join(result.reasons) if result.reasons else ''
                writer.writerow([result.mint, status, reasons])
        
        logger.info(f"Экспортировано {len(results)} результатов в {self.csv_file}")

        return self.csv_file
