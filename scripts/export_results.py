import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.storage import Storage


async def main():
    storage = Storage(data_dir="data")
    await storage.initialize()
    
    print("Экспорт результатов в CSV...")
    csv_path = await storage.export_to_csv()
    
    results = await storage.get_all_results()
    scam_count = sum(1 for r in results if r.is_scam)
    
    print(f"Экспортировано {len(results)} токенов")
    print(f"   - Scam: {scam_count}")
    print(f"   - Clean: {len(results) - scam_count}")
    print(f"   - Файл: {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())