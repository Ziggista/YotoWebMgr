from app.models import LibraryItem, PlaylistTrack


def build_playlist_preview(item: LibraryItem, tracks: list[PlaylistTrack]) -> dict[str, object]:
    chapters: list[dict[str, object]] = []
    for track in tracks:
        chapter: dict[str, object] = {
            "title": track.title,
            "display_number": track.track_number,
            "duration_seconds": track.duration_seconds,
            "track_behavior": track.track_behavior,
            "icon_path": track.icon_path,
        }
        if track.is_stream:
            chapter["type"] = "stream"
            chapter["stream_url"] = track.stream_url
            chapter["offline_available"] = False
        else:
            chapter["type"] = "audio"
            chapter["source_path"] = track.source_path
            chapter["source_url"] = track.source_url
            chapter["offline_available"] = True
        chapters.append(chapter)

    return {
        "title": item.title,
        "cover_art_path": item.cover_art_path,
        "playback": {
            "always_play_from_start": item.playlist_always_play_from_start,
            "shuffle_tracks": item.playlist_shuffle_tracks,
            "hide_track_numbers": item.playlist_hide_track_numbers,
        },
        "chapters": chapters,
    }
