import logging
import os
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError
from app.models import HeliusTransaction, ScamDetectionResult
from app.detector import ScamDetector
from app.storage import Storage
from app.helius_client import HeliusClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

storage = None
detector = None
helius_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global storage, detector, helius_client
    
    logger.info("Инициализация приложения...")
    
    helius_api_key = os.getenv("HELIUS_API_KEY", "")
    helius_client = HeliusClient(api_key=helius_api_key)
    
    storage = Storage(data_dir="data")
    await storage.initialize()
    
    detector = ScamDetector(storage=storage, helius_client=helius_client)
    
    logger.info("Приложение готово к работе!")
    logger.info("Webhook URL: http://109.69.59.66/webhook")
    
    yield
    
    logger.info("Завершение работы...")

    
app = FastAPI(
    title="Solana Scam Token Detector",
    description="Детектор скам-токенов pump.fun",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "Solana Scam Detector",
        "version": "1.0.0"
    }


@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        body = await request.json()
        
        if not isinstance(body, list):
            body = [body]
        
        total_received = len(body)
        processed = 0
        filtered_out = 0
        all_results = []
        
        for tx_data in body:
            try:
                tx_type = tx_data.get('type', '')
                tx_source = tx_data.get('source', '')
                signature = tx_data.get('signature', 'N/A')
                
                if 'NFT' in tx_type:
                    logger.debug(f"⏭️ Пропущена NFT: {tx_type}")
                    filtered_out += 1
                    continue
                
                if tx_source != 'PUMP_FUN':
                    logger.debug(f"⏭️ Пропущен источник: {tx_source}")
                    filtered_out += 1
                    continue
                
                logger.info(f"📥 Обработка: {signature[:16]}... [{tx_type}]")
                
                transaction = HeliusTransaction(**tx_data)
                
                results = await detector.analyze_transaction(transaction)
                
                for r in results:
                    if r.is_scam:
                        logger.warning(
                            f"🚨 SCAM: {r.mint[:16]}... - {', '.join(r.reasons)}"
                        )
                    else:
                        logger.info(f"✅ Clean: {r.mint[:16]}...")
                
                all_results.extend(results)
                processed += 1
                
            except ValidationError as e:
                logger.error(f"❌ Ошибка валидации: {e}")
                filtered_out += 1
                continue
            except Exception as e:
                logger.error(f"❌ Ошибка обработки: {e}", exc_info=True)
                filtered_out += 1
                continue
        
        return {
            "status": "success",
            "total_received": total_received,
            "processed": processed,
            "filtered_out": filtered_out,
            "tokens_analyzed": len(all_results)
        }
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/token/{mint}")
async def get_token_status(mint: str):
    try:
        result = await storage.get_result(mint)
        if not result:
            raise HTTPException(status_code=404, detail="Токен не найден")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения токена: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    try:
        results = await storage.get_all_results()
        
        total = len(results)
        scam_count = sum(1 for r in results if r.is_scam)
        clean_count = total - scam_count
        
        bundle_count = sum(1 for r in results if r.has_bundle)
        large_purchase_count = sum(1 for r in results if r.has_large_purchase)
        invalid_metadata_count = sum(1 for r in results if r.invalid_metadata_url)
        invalid_suffix_count = sum(1 for r in results if r.invalid_mint_suffix)
        
        return {
            "total_tokens": total,
            "scam_tokens": scam_count,
            "clean_tokens": clean_count,
            "scam_percentage": round(scam_count / total * 100, 2) if total > 0 else 0,
            "patterns": {
                "bundles": bundle_count,
                "large_purchases": large_purchase_count,
                "invalid_metadata": invalid_metadata_count,
                "invalid_suffix": invalid_suffix_count
            }
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/export")
async def export_results():
    """Экспортировать результаты в CSV"""
    try:
        csv_path = await storage.export_to_csv()
        results = await storage.get_all_results()
        
        return {
            "status": "success",
            "path": csv_path,
            "total_tokens": len(results),
            "scam_tokens": sum(1 for r in results if r.is_scam)
        }
    except Exception as e:
        logger.error(f"Ошибка экспорта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
