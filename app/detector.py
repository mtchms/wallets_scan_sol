import logging
from typing import List, Tuple, Optional

from app.models import HeliusTransaction, ScamDetectionResult
from app.helius_client import HeliusClient
from app.storage import Storage

logger = logging.getLogger(__name__)

LAMPORTS_PER_SOL = 1_000_000_000
BUNDLE_INDEX_THRESHOLD = 30
LARGE_PURCHASE_THRESHOLD_SOL = 30.0
PUMP_SUFFIX = "pump"


class ScamDetector:
    
    def __init__(self, storage: Storage, helius_client: HeliusClient):
        self.storage = storage
        self.helius_client = helius_client
    
    async def analyze_transaction(
        self, 
        transaction: HeliusTransaction
    ) -> List[ScamDetectionResult]:

        results = []
        
        mints = self._extract_mints(transaction)
        
        if not mints:
            logger.debug("Транзакция не содержит токенов")
            return results
        
        for mint in mints:
            await self.storage.add_transaction(mint, transaction)
            
            token_transactions = await self.storage.get_token_transactions(mint)
            
            result = await self._analyze_token(mint, token_transactions, transaction)
            results.append(result)
            
            await self.storage.save_result(result)
        
        return results
    
    def _extract_mints(self, transaction: HeliusTransaction) -> List[str]:
        mints = set()
        
        for transfer in transaction.tokenTransfers:
            if transfer.mint:
                mints.add(transfer.mint)
        
        for account_data in transaction.accountData:
            for balance_change in account_data.tokenBalanceChanges:
                if balance_change.mint:
                    mints.add(balance_change.mint)
        
        return list(mints)
    
    async def _analyze_token(
        self, 
        mint: str, 
        transactions: List[HeliusTransaction],
        current_tx: HeliusTransaction
    ) -> ScamDetectionResult:
        is_scam = False
        reasons = []
        
        has_bundle, bundle_gap = self._check_bundle_pattern(transactions)
        if has_bundle:
            is_scam = True
            reasons.append(f"Бандл с девом (индекс: {bundle_gap})")
        
        has_large_purchase, max_sol = self._check_large_purchase(transactions)
        if has_large_purchase:
            is_scam = True
            reasons.append(f"Большая покупка: {max_sol:.2f} SOL")
        
        invalid_metadata = await self._check_metadata_url(mint)
        if invalid_metadata:
            is_scam = True
            reasons.append("Некорректная URL метадаты (не ipfs.io)")
        
        invalid_suffix = self._check_mint_suffix(mint)
        if invalid_suffix:
            is_scam = True
            reasons.append(f"Минт не заканчивается на '{PUMP_SUFFIX}'")
        
        timestamps = [tx.timestamp for tx in transactions]
        first_seen = min(timestamps) if timestamps else current_tx.timestamp
        
        return ScamDetectionResult(
            mint=mint,
            is_scam=is_scam,
            reasons=reasons,
            flags={},
            has_bundle=has_bundle,
            has_large_purchase=has_large_purchase,
            invalid_metadata_url=invalid_metadata,
            invalid_mint_suffix=invalid_suffix,
            single_token_dev=None,
            max_purchase_sol=max_sol,
            bundle_index_gap=bundle_gap,
            total_transactions=len(transactions),
            first_seen=first_seen,
            last_updated=current_tx.timestamp
        )
    
    def _check_bundle_pattern(
        self, 
        transactions: List[HeliusTransaction]
    ) -> Tuple[bool, Optional[int]]:
        if len(transactions) < 2:
            return False, None
        
        slots_txs = {}
        for tx in transactions:
            if tx.slot not in slots_txs:
                slots_txs[tx.slot] = []
            slots_txs[tx.slot].append(tx)
        
        for slot, txs in slots_txs.items():
            if len(txs) >= 2:
                logger.info(f"🔍 Найдено {len(txs)} транзакций в слоте {slot}")
                return True, len(txs)
        
        return False, None
    
    def _check_large_purchase(
        self, 
        transactions: List[HeliusTransaction]
    ) -> Tuple[bool, Optional[float]]:
        max_sol_amount = 0.0
        
        for tx in transactions:
            for transfer in tx.nativeTransfers:
                sol_amount = transfer.amount / LAMPORTS_PER_SOL
                if sol_amount > max_sol_amount:
                    max_sol_amount = sol_amount
        
        has_large = max_sol_amount > LARGE_PURCHASE_THRESHOLD_SOL
        return has_large, max_sol_amount if has_large else None
    
    async def _check_metadata_url(self, mint: str) -> bool:
        try:
            metadata = await self.helius_client.get_token_metadata(mint)
            if not metadata or not metadata.uri:
                return False
            
            uri = metadata.uri.lower()
            if not uri.startswith("https://ipfs.io/"):
                logger.warning(f"⚠️ Токен {mint[:16]}... некорректная URI: {metadata.uri}")
                return True
            
            return False
        except Exception as e:
            logger.debug(f"Не удалось получить метадату для {mint[:16]}...: {e}")
            return False
    
    def _check_mint_suffix(self, mint: str) -> bool:
        return not mint.endswith(PUMP_SUFFIX)
