from app.db.base import Base
from app.models import (
    ArtworkAsset,
    CardPlanPart,
    CardPlanTrackAssignment,
    ImportRequest,
    Job,
    LibraryItem,
    PhysicalCard,
    PlaylistTrack,
    PodcastEpisode,
    PodcastFeed,
    ProcessedAsset,
    Setting,
    SplitPoint,
    Tag,
    TagAssignment,
    User,
    VersionEvent,
    YotoPlaylistDraft,
)


def test_user_model_is_registered_in_metadata() -> None:
    table = Base.metadata.tables["users"]

    assert User.__tablename__ == "users"
    assert {"slug", "display_name", "username", "password_hash"}.issubset(table.columns.keys())
    assert table.columns["slug"].unique is True
    assert table.columns["username"].unique is True


def test_foundation_models_are_registered_in_metadata() -> None:
    assert LibraryItem.__tablename__ in Base.metadata.tables
    assert ArtworkAsset.__tablename__ in Base.metadata.tables
    assert CardPlanPart.__tablename__ in Base.metadata.tables
    assert CardPlanTrackAssignment.__tablename__ in Base.metadata.tables
    assert ImportRequest.__tablename__ in Base.metadata.tables
    assert Job.__tablename__ in Base.metadata.tables
    assert PhysicalCard.__tablename__ in Base.metadata.tables
    assert PlaylistTrack.__tablename__ in Base.metadata.tables
    assert PodcastFeed.__tablename__ in Base.metadata.tables
    assert PodcastEpisode.__tablename__ in Base.metadata.tables
    assert ProcessedAsset.__tablename__ in Base.metadata.tables
    assert SplitPoint.__tablename__ in Base.metadata.tables
    assert Tag.__tablename__ in Base.metadata.tables
    assert TagAssignment.__tablename__ in Base.metadata.tables
    assert Setting.__tablename__ in Base.metadata.tables
    assert VersionEvent.__tablename__ in Base.metadata.tables
    assert YotoPlaylistDraft.__tablename__ in Base.metadata.tables
