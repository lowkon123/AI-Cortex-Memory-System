import asyncio
import asyncpg

async def rebuild():
    print("Connecting to database...")
    conn = await asyncpg.connect(
        host="localhost", 
        port=5432, 
        database="cortex_memory", 
        user="cortex_user", 
        password="cortex_pass"
    )
    print("Dropping memories table...")
    await conn.execute("DROP TABLE IF EXISTS memories")
    print("Table dropped successfully")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(rebuild())
