"""Skeleton smoke test — confirms the package imports cleanly."""


def test_packages_import():
    import src  # noqa: F401
    import src.core  # noqa: F401
    import src.agents  # noqa: F401
    import src.tools  # noqa: F401
    import src.ingestion  # noqa: F401
    import src.normalization  # noqa: F401
    import src.publishing  # noqa: F401
    import src.api  # noqa: F401
