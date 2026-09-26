from sqlalchemy import text


async def test_gimprod_schema_is_loaded(db_session):
    result = await db_session.execute(
        text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'gimprod'")
    )
    assert result.scalar_one() == 14


async def test_client_table_lives_in_matriculacion(db_session):
    result = await db_session.execute(
        text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'matriculacion' AND table_name = 'client'"
        )
    )
    assert result.scalar_one() == 1
