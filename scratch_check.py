import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(host='localhost', port=5432, database='cortex_memory', user='cortex_user', password='cortex_pass')
    rows = await conn.fetch("SELECT content, summary_l0, importance FROM memories")
    for r in rows:
        print(dict(r))
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
