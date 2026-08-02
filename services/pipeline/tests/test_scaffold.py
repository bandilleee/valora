from valora_pipeline.scaffold import ping


def test_ping() -> None:
    assert ping() == "pong"
