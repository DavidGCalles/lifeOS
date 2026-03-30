import pytest
from sqlmodel import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Database connection string for the local 'lifeos_postgres' container
# Format: dialect+driver://username:password@host:port/database
DATABASE_URL = "postgresql+asyncpg://lifeos_user:o7REwN6B5veABfQM@localhost:5432/lifeos_db"

@pytest.mark.asyncio
async def test_postgres_connection():
    """Test that the PostgreSQL database is up and accessible."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    try:
        async with AsyncSession(engine) as session:
            # Execute a simple query to verify connectivity
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            
            assert value == 1, f"Expected 1, got {value}"
            
    except Exception as e:
        pytest.fail(f"Failed to connect to the database. Error details: {e}")
        
    finally:
        # Dispose of the engine cleanly
        await engine.dispose()
