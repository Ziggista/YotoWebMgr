import { FormEvent, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";
import AudioPlayer from "react-h5-audio-player";
import "react-h5-audio-player/lib/styles.css";
import {
  AppSettings,
  AuthProvidersResponse,
  CardPlan,
  ImportSourceInfo,
  ImportRequest,
  Job,
  LibraryItemDetail,
  LibraryItem,
  PhysicalCard,
  ReadinessResponse,
  SessionResponse,
  Tag,
  VersionEvent,
  YotoCredentialStatus,
  YotoPlaylistDraft,
  YotoPlaylistVersion,
  applyTrackIcon,
  createCard,
  createImport,
  createTag,
  createPodcastFeed,
  createRadioStreamTrack,
  createSplitPoint,
  disconnectYotoCredentials,
  fetchCards,
  fetchCardPlan,
  fetchImportSources,
  fetchImports,
  fetchJobs,
  fetchLibraryItemDetail,
  fetchLibraryItems,
  fetchLibraryItemVersions,
  fetchReadiness,
  fetchSavedCardPlan,
  fetchSettings,
  fetchTags,
  fetchYotoCredentialStatus,
  fetchYotoPlaylists,
  fetchYotoPlaylistVersions,
  hideImport,
  fetchAuthProviders,
  linkLibraryItemToCard,
  loginWithPassword,
  quickSelectUser,
  queueArtworkPixelise,
  queueLibraryItemProcessing,
  queueYotoPlaylist,
  restoreLibraryItemVersion,
  restoreYotoPlaylistVersion,
  retryJob,
  saveCardPlan,
  setLibraryItemTags,
  startYotoOAuth,
  updatePlaylistTrack,
  updateLibraryItemSettings,
  updateSettings,
  uploadCoverArt,
  uploadImport,
} from "./api";
import "./App.css";

const sections = ["Library", "Import", "Cards", "Jobs", "Tags", "Settings"];
const sessionStorageKey = "yotowebmgr.session";
const contentTypes = [
  "Audiobook",
  "Music Album",
  "Story Collection",
  "Podcast",
  "Radio Play",
  "Sleep Sounds",
  "Custom Playlist",
  "Other Audio",
];
const defaultNdefFormatCommand = "A2:03:E1:10:06:00,A2:04:03:04:D8:00,A2:05:00:00:FE:00";

function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="panel">
      <p className="eyebrow">Milestone 1</p>
      <h2>{title}</h2>
      <p>
        This area is scaffolded and ready for feature work. The initial focus is authentication,
        library data, job orchestration, and import flows.
      </p>
    </section>
  );
}

function EmptyState({ message }: { message: string }) {
  return <p className="muted">{message}</p>;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "Unknown";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

function cardPlanAssignments(plan: CardPlan | null): Record<number, number> {
  const assignments: Record<number, number> = {};
  plan?.parts.forEach((part) => {
    part.tracks.forEach((track) => {
      assignments[track.track_id] = part.part_number;
    });
  });
  return assignments;
}

function LibraryPage() {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [filters, setFilters] = useState({ search: "", content_type: "", tag_id: "" });
  const [cards, setCards] = useState<PhysicalCard[]>([]);
  const [activeLinkItemId, setActiveLinkItemId] = useState<number | null>(null);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [detail, setDetail] = useState<LibraryItemDetail | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [coverArtPath, setCoverArtPath] = useState("");
  const [coverArtFile, setCoverArtFile] = useState<File | null>(null);
  const [trackIconPath, setTrackIconPath] = useState("");
  const [radioForm, setRadioForm] = useState({ title: "", stream_url: "", icon_path: "" });
  const [podcastForm, setPodcastForm] = useState({ title: "", rss_url: "" });
  const [splitForm, setSplitForm] = useState({ timestamp_seconds: "", title: "", part_number: "" });
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [linkMessage, setLinkMessage] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);

  async function refreshLibraryList() {
    const nextItems = await fetchLibraryItems({
      search: filters.search.trim() || undefined,
      content_type: filters.content_type || undefined,
      tag_id: filters.tag_id ? Number(filters.tag_id) : null,
    });
    setItems(nextItems);
  }

  useEffect(() => {
    void Promise.all([refreshLibraryList(), fetchTags().then(setTags)])
      .then(() => undefined)
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load library."),
      );
  }, [filters.search, filters.content_type, filters.tag_id]);

  async function openLinkPanel(itemId: number) {
    setError(null);
    setLinkMessage(null);
    setActiveLinkItemId(itemId);
    try {
      const nextCards = cards.length > 0 ? cards : await fetchCards();
      setCards(nextCards);
      setSelectedCardId(nextCards[0] ? String(nextCards[0].id) : "");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load cards.");
    }
  }

  async function openDetailPanel(itemId: number) {
    setError(null);
    setLinkMessage(null);
    setDetailLoading(true);
    try {
      const [nextDetail, nextReadiness] = await Promise.all([
        fetchLibraryItemDetail(itemId),
        fetchReadiness(itemId),
      ]);
      setDetail(nextDetail);
      setReadiness(nextReadiness);
      setCoverArtPath(nextDetail.item.cover_art_path ?? "");
      setCoverArtFile(null);
      setTrackIconPath("");
      setSelectedTagIds(nextDetail.item.tags.map((tag) => tag.id));
      setRadioForm({ title: "", stream_url: "", icon_path: "" });
      setPodcastForm({ title: "", rss_url: "" });
      setSplitForm({ timestamp_seconds: "", title: "", part_number: "" });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load item detail.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function refreshDetail(itemId: number) {
    const [nextDetail, nextReadiness] = await Promise.all([
      fetchLibraryItemDetail(itemId),
      fetchReadiness(itemId),
    ]);
    setDetail(nextDetail);
    setReadiness(nextReadiness);
    setItems((current) =>
      current.map((item) => (item.id === nextDetail.item.id ? nextDetail.item : item)),
    );
    setSelectedTagIds(nextDetail.item.tags.map((tag) => tag.id));
  }

  async function handleSavePlaylistSettings() {
    if (!detail) return;
    setError(null);
    try {
      const updated = await updateLibraryItemSettings(detail.item.id, {
        cover_art_path: coverArtPath || null,
        playlist_always_play_from_start: detail.item.playlist_always_play_from_start,
        playlist_shuffle_tracks: detail.item.playlist_shuffle_tracks,
        playlist_hide_track_numbers: detail.item.playlist_hide_track_numbers,
      });
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      await refreshDetail(updated.id);
      setLinkMessage("Playlist settings saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save settings.");
    }
  }

  async function handleUploadCoverArt() {
    if (!detail || !coverArtFile) return;
    setError(null);
    try {
      const updated = await uploadCoverArt(detail.item.id, coverArtFile);
      setCoverArtPath(updated.cover_art_path ?? "");
      setCoverArtFile(null);
      await refreshDetail(updated.id);
      setLinkMessage("Cover artwork uploaded.");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Failed to upload cover art.");
    }
  }

  function setDetailOption(
    key:
      | "playlist_always_play_from_start"
      | "playlist_shuffle_tracks"
      | "playlist_hide_track_numbers",
    value: boolean,
  ) {
    setDetail((current) =>
      current ? { ...current, item: { ...current.item, [key]: value } } : current,
    );
  }

  async function handleApplyIcon() {
    if (!detail || !trackIconPath) return;
    setError(null);
    try {
      await applyTrackIcon(detail.item.id, trackIconPath);
      await refreshDetail(detail.item.id);
      setLinkMessage("Track icon applied.");
    } catch (iconError) {
      setError(iconError instanceof Error ? iconError.message : "Failed to apply icon.");
    }
  }

  async function handleSaveTags() {
    if (!detail) return;
    setError(null);
    try {
      await setLibraryItemTags(detail.item.id, selectedTagIds);
      await Promise.all([refreshDetail(detail.item.id), refreshLibraryList(), fetchTags().then(setTags)]);
      setLinkMessage("Tags saved.");
    } catch (tagError) {
      setError(tagError instanceof Error ? tagError.message : "Failed to save tags.");
    }
  }

  async function handleUpdateTrack(event: FormEvent<HTMLFormElement>, trackId: number) {
    event.preventDefault();
    if (!detail) return;
    const formData = new FormData(event.currentTarget);
    const durationValue = String(formData.get("duration_seconds") ?? "");
    const sourceUrl = String(formData.get("source_url") ?? "").trim();
    const streamUrl = String(formData.get("stream_url") ?? "").trim();

    setError(null);
    try {
      await updatePlaylistTrack(detail.item.id, trackId, {
        title: String(formData.get("title") ?? ""),
        source_url: sourceUrl || null,
        track_number: Number(formData.get("track_number") ?? 1),
        duration_seconds: durationValue ? Number(durationValue) : null,
        icon_path: String(formData.get("icon_path") ?? "").trim() || null,
        track_behavior: String(formData.get("track_behavior") ?? "continue"),
        stream_url: streamUrl || null,
      });
      await refreshDetail(detail.item.id);
      setLinkMessage("Track saved.");
    } catch (trackError) {
      setError(trackError instanceof Error ? trackError.message : "Failed to save track.");
    }
  }

  async function handleAddRadioStream(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setError(null);
    try {
      await createRadioStreamTrack(detail.item.id, {
        title: radioForm.title,
        stream_url: radioForm.stream_url,
        icon_path: radioForm.icon_path || null,
      });
      await refreshDetail(detail.item.id);
      setRadioForm({ title: "", stream_url: "", icon_path: "" });
      setLinkMessage("Radio stream saved and validation queued.");
    } catch (radioError) {
      setError(radioError instanceof Error ? radioError.message : "Failed to add radio stream.");
    }
  }

  async function handleAddPodcast(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setError(null);
    try {
      await createPodcastFeed(detail.item.id, {
        title: podcastForm.title || null,
        rss_url: podcastForm.rss_url,
      });
      await refreshDetail(detail.item.id);
      setPodcastForm({ title: "", rss_url: "" });
      setLinkMessage("Podcast feed saved and inspection queued.");
    } catch (podcastError) {
      setError(podcastError instanceof Error ? podcastError.message : "Failed to add podcast.");
    }
  }

  async function handleAddSplitPoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setError(null);
    try {
      await createSplitPoint(detail.item.id, {
        timestamp_seconds: Number(splitForm.timestamp_seconds),
        title: splitForm.title,
        part_number: splitForm.part_number ? Number(splitForm.part_number) : null,
      });
      await refreshDetail(detail.item.id);
      setSplitForm({ timestamp_seconds: "", title: "", part_number: "" });
      setLinkMessage("Split point saved.");
    } catch (splitError) {
      setError(splitError instanceof Error ? splitError.message : "Failed to save split point.");
    }
  }

  async function handleLinkToCard(itemId: number) {
    if (!selectedCardId) {
      setError("Choose a card first.");
      return;
    }

    setLinking(true);
    setError(null);
    setLinkMessage(null);
    try {
      const result = await linkLibraryItemToCard(itemId, Number(selectedCardId));
      setItems((current) =>
        current.map((item) => (item.id === result.library_item.id ? result.library_item : item)),
      );
      setCards((current) =>
        current.map((card) => (card.id === result.card.id ? result.card : card)),
      );
      setLinkMessage(
        result.requires_split_plan
          ? `Queued card planning for ${result.card.display_name}.`
          : `Queued Yoto upload for ${result.card.display_name}.`,
      );
      setActiveLinkItemId(null);
    } catch (linkError) {
      setError(linkError instanceof Error ? linkError.message : "Failed to link card.");
    } finally {
      setLinking(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Library</p>
          <h2>Media library</h2>
        </div>
        <span className="status-pill">{items.length} items</span>
      </div>
      {error ? <p className="auth-error">{error}</p> : null}
      <div className="filter-bar">
        <input
          onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
          placeholder="Search library"
          value={filters.search}
        />
        <select
          onChange={(event) => setFilters((current) => ({ ...current, content_type: event.target.value }))}
          value={filters.content_type}
        >
          <option value="">All types</option>
          {contentTypes.map((contentType) => (
            <option key={contentType} value={contentType}>
              {contentType}
            </option>
          ))}
        </select>
        <select
          onChange={(event) => setFilters((current) => ({ ...current, tag_id: event.target.value }))}
          value={filters.tag_id}
        >
          <option value="">All tags</option>
          {tags.map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </select>
      </div>
      {items.length === 0 ? (
        <EmptyState message="No library items yet. Create an import to seed the library." />
      ) : (
        <div className="item-list">
          {items.map((item) => (
            <article className="list-row" key={item.id}>
              <div>
                <h3>{item.title}</h3>
                <p className="muted">
                  {item.content_type} · {item.status}
                  {item.stream_url ? " · Live stream" : ""}
                </p>
                {item.tags.length > 0 ? (
                  <div className="tag-chip-row">
                    {item.tags.map((tag) => (
                      <span className="tag-chip" key={tag.id} style={{ borderColor: tag.color ?? undefined }}>
                        {tag.name}
                      </span>
                    ))}
                  </div>
                ) : null}
                {item.media_url || item.stream_url ? (
                  <div className="library-player">
                    <AudioPlayer
                      customAdditionalControls={[]}
                      customVolumeControls={[]}
                      layout="horizontal-reverse"
                      preload={item.stream_url ? "none" : "metadata"}
                      showJumpControls={false}
                      src={item.media_url ?? item.stream_url ?? undefined}
                    />
                  </div>
                ) : null}
                {activeLinkItemId === item.id ? (
                  <div className="inline-link-panel">
                    {cards.length === 0 ? (
                      <p className="muted">No cards available yet.</p>
                    ) : (
                      <label>
                        Card
                        <select
                          onChange={(event) => setSelectedCardId(event.target.value)}
                          value={selectedCardId}
                        >
                          {cards.map((card) => (
                            <option key={card.id} value={card.id}>
                              {card.display_name} ({card.card_code})
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    <div className="row-actions">
                      <button
                        className="primary-button"
                        disabled={linking || cards.length === 0}
                        onClick={() => void handleLinkToCard(item.id)}
                        type="button"
                      >
                        {linking ? "Queueing" : "Queue link"}
                      </button>
                      <button
                        className="ghost-button"
                        onClick={() => setActiveLinkItemId(null)}
                        type="button"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="row-actions">
                <Link className="ghost-button" to={`/library/${item.id}`}>
                  Details
                </Link>
                <button
                  className="ghost-button"
                  onClick={() => void openDetailPanel(item.id)}
                  type="button"
                >
                  Options
                </button>
                <button
                  className="ghost-button"
                  onClick={() => void openLinkPanel(item.id)}
                  type="button"
                >
                  Link to card
                </button>
                <span className="status-pill status-pill-muted">#{item.id}</span>
              </div>
            </article>
          ))}
        </div>
      )}
      {detail ? (
        <div className="detail-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Card prep</p>
              <h2>{detail.item.title}</h2>
            </div>
            <button className="ghost-button" onClick={() => setDetail(null)} type="button">
              Close
            </button>
          </div>

          <div className="prep-grid">
            <div className="prep-block">
              <h3>Playlist options</h3>
              <label>
                Cover path
                <input
                  onChange={(event) => setCoverArtPath(event.target.value)}
                  placeholder="/artwork/moon.png"
                  value={coverArtPath}
                />
              </label>
              <label className="file-picker compact-file-picker">
                <span>{coverArtFile ? coverArtFile.name : "Choose cover image"}</span>
                <input
                  accept=".jpg,.jpeg,.png,.webp"
                  onChange={(event) => setCoverArtFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </label>
              <button
                className="ghost-button"
                disabled={!coverArtFile}
                onClick={() => void handleUploadCoverArt()}
                type="button"
              >
                Upload cover
              </button>
              <label className="checkbox-row">
                <input
                  checked={detail.item.playlist_always_play_from_start}
                  onChange={(event) =>
                    setDetailOption("playlist_always_play_from_start", event.target.checked)
                  }
                  type="checkbox"
                />
                Always play from start
              </label>
              <label className="checkbox-row">
                <input
                  checked={detail.item.playlist_shuffle_tracks}
                  onChange={(event) =>
                    setDetailOption("playlist_shuffle_tracks", event.target.checked)
                  }
                  type="checkbox"
                />
                Shuffle tracks
              </label>
              <label className="checkbox-row">
                <input
                  checked={detail.item.playlist_hide_track_numbers}
                  onChange={(event) =>
                    setDetailOption("playlist_hide_track_numbers", event.target.checked)
                  }
                  type="checkbox"
                />
                Hide track numbers
              </label>
              <button className="primary-button" onClick={() => void handleSavePlaylistSettings()} type="button">
                Save options
              </button>
            </div>

            <div className="prep-block">
              <h3>Tags</h3>
              {tags.length === 0 ? (
                <EmptyState message="No tags available yet." />
              ) : (
                <div className="tag-checkbox-list">
                  {tags.map((tag) => (
                    <label className="checkbox-row" key={tag.id}>
                      <input
                        checked={selectedTagIds.includes(tag.id)}
                        onChange={(event) =>
                          setSelectedTagIds((current) =>
                            event.target.checked
                              ? Array.from(new Set([...current, tag.id]))
                              : current.filter((tagId) => tagId !== tag.id),
                          )
                        }
                        type="checkbox"
                      />
                      {tag.name}
                    </label>
                  ))}
                </div>
              )}
              <button className="primary-button" onClick={() => void handleSaveTags()} type="button">
                Save tags
              </button>
            </div>

            <div className="prep-block">
              <h3>Track icons</h3>
              <label>
                Icon path
                <input
                  onChange={(event) => setTrackIconPath(event.target.value)}
                  placeholder="/icons/book.png"
                  value={trackIconPath}
                />
              </label>
              <button
                className="ghost-button"
                disabled={!trackIconPath || detail.tracks.length === 0}
                onClick={() => void handleApplyIcon()}
                type="button"
              >
                Apply to all tracks
              </button>
              <p className="muted">
                {detail.tracks.length} tracks ·{" "}
                {detail.tracks.filter((track) => !track.icon_path).length} missing icons
              </p>
            </div>

            <form className="prep-block" onSubmit={(event) => void handleAddRadioStream(event)}>
              <h3>Radio stream</h3>
              <input
                onChange={(event) =>
                  setRadioForm((current) => ({ ...current, title: event.target.value }))
                }
                placeholder="Stream title"
                required
                value={radioForm.title}
              />
              <input
                onChange={(event) =>
                  setRadioForm((current) => ({ ...current, stream_url: event.target.value }))
                }
                placeholder="https://example.test/stream.mp3"
                required
                value={radioForm.stream_url}
              />
              <input
                onChange={(event) =>
                  setRadioForm((current) => ({ ...current, icon_path: event.target.value }))
                }
                placeholder="/icons/radio.png"
                value={radioForm.icon_path}
              />
              <button className="primary-button" type="submit">
                Add stream
              </button>
            </form>

            <form className="prep-block" onSubmit={(event) => void handleAddPodcast(event)}>
              <h3>Podcast feed</h3>
              <input
                onChange={(event) =>
                  setPodcastForm((current) => ({ ...current, title: event.target.value }))
                }
                placeholder="Optional title"
                value={podcastForm.title}
              />
              <input
                onChange={(event) =>
                  setPodcastForm((current) => ({ ...current, rss_url: event.target.value }))
                }
                placeholder="https://example.test/feed.xml"
                required
                value={podcastForm.rss_url}
              />
              <button className="primary-button" type="submit">
                Add feed
              </button>
            </form>

            <form className="prep-block" onSubmit={(event) => void handleAddSplitPoint(event)}>
              <h3>Manual split point</h3>
              <input
                min="0"
                onChange={(event) =>
                  setSplitForm((current) => ({ ...current, timestamp_seconds: event.target.value }))
                }
                placeholder="Timestamp seconds"
                required
                type="number"
                value={splitForm.timestamp_seconds}
              />
              <input
                onChange={(event) =>
                  setSplitForm((current) => ({ ...current, title: event.target.value }))
                }
                placeholder="Part title"
                required
                value={splitForm.title}
              />
              <input
                min="1"
                onChange={(event) =>
                  setSplitForm((current) => ({ ...current, part_number: event.target.value }))
                }
                placeholder="Part number"
                type="number"
                value={splitForm.part_number}
              />
              <button className="primary-button" type="submit">
                Save split
              </button>
            </form>

            <div className="prep-block">
              <h3>Readiness</h3>
              {detailLoading ? <p className="muted">Loading checks...</p> : null}
              {readiness ? (
                <div className="check-list">
                  {readiness.checks.map((check) => (
                    <div className="check-row" key={check.key}>
                      <span className={check.ok ? "check-ok" : "check-warn"}>
                        {check.ok ? "OK" : "Needs review"}
                      </span>
                      <div>
                        <strong>{check.label}</strong>
                        <p className="muted">{check.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="track-editor-panel">
            <div className="section-header">
              <div>
                <p className="eyebrow">Tracks</p>
                <h2>Track editor</h2>
              </div>
              <span className="status-pill">{detail.tracks.length} tracks</span>
            </div>
            {detail.tracks.length === 0 ? (
              <EmptyState message="No tracks yet. Add a radio stream or import a ZIP album to create track rows." />
            ) : (
              <div className="track-editor-list">
                {detail.tracks.map((track) => (
                  <form
                    className="track-editor-row"
                    key={track.id}
                    onSubmit={(event) => void handleUpdateTrack(event, track.id)}
                  >
                    <label>
                      Title
                      <input defaultValue={track.title} name="title" required />
                    </label>
                    <label>
                      Order
                      <input
                        defaultValue={track.track_number}
                        min="1"
                        name="track_number"
                        required
                        type="number"
                      />
                    </label>
                    <label>
                      Behavior
                      <select defaultValue={track.track_behavior} name="track_behavior">
                        <option value="continue">Continue</option>
                        <option value="pause_for_button">Pause for button</option>
                        <option value="repeat_track">Repeat track</option>
                      </select>
                    </label>
                    <label>
                      Duration seconds
                      <input
                        defaultValue={track.duration_seconds ?? ""}
                        min="0"
                        name="duration_seconds"
                        type="number"
                      />
                    </label>
                    <label>
                      Icon path
                      <input defaultValue={track.icon_path ?? ""} name="icon_path" />
                    </label>
                    <label>
                      Source URL
                      <input defaultValue={track.source_url ?? ""} name="source_url" />
                    </label>
                    <label>
                      Stream URL
                      <input defaultValue={track.stream_url ?? ""} name="stream_url" />
                    </label>
                    <div className="track-editor-actions">
                      <span className="status-pill status-pill-muted">
                        {track.is_stream ? "Stream" : `Track ${track.track_number}`}
                      </span>
                      <button className="primary-button" type="submit">
                        Save track
                      </button>
                    </div>
                  </form>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
      {linkMessage ? <p className="muted">{linkMessage}</p> : null}
    </section>
  );
}

function LibraryDetailPage() {
  const { itemId } = useParams();
  const numericItemId = Number(itemId);
  const [detail, setDetail] = useState<LibraryItemDetail | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [cardPlan, setCardPlan] = useState<CardPlan | null>(null);
  const [savedCardPlan, setSavedCardPlan] = useState<CardPlan | null>(null);
  const [cardPlanDraft, setCardPlanDraft] = useState<Record<number, number>>({});
  const [versions, setVersions] = useState<VersionEvent[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [yotoPlaylists, setYotoPlaylists] = useState<YotoPlaylistDraft[]>([]);
  const [yotoPlaylistVersions, setYotoPlaylistVersions] = useState<Record<number, YotoPlaylistVersion[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshPage() {
    if (!Number.isFinite(numericItemId)) {
      throw new Error("Invalid library item.");
    }
    const [
      nextDetail,
      nextReadiness,
      nextCardPlan,
      nextSavedCardPlan,
      nextVersions,
      nextJobs,
      nextYotoPlaylists,
    ] = await Promise.all([
      fetchLibraryItemDetail(numericItemId),
      fetchReadiness(numericItemId),
      fetchCardPlan(numericItemId),
      fetchSavedCardPlan(numericItemId),
      fetchLibraryItemVersions(numericItemId),
      fetchJobs(),
      fetchYotoPlaylists(numericItemId),
    ]);
    setDetail(nextDetail);
    setReadiness(nextReadiness);
    setCardPlan(nextCardPlan);
    setSavedCardPlan(nextSavedCardPlan);
    setCardPlanDraft(cardPlanAssignments(nextSavedCardPlan.parts.length > 0 ? nextSavedCardPlan : nextCardPlan));
    setVersions(nextVersions);
    setJobs(nextJobs.filter((job) => job.related_library_item_id === numericItemId));
    setYotoPlaylists(nextYotoPlaylists);
    const versionEntries = await Promise.all(
      nextYotoPlaylists.map(async (playlist) => [playlist.id, await fetchYotoPlaylistVersions(playlist.id)] as const),
    );
    setYotoPlaylistVersions(Object.fromEntries(versionEntries));
  }

  useEffect(() => {
    setLoading(true);
    void refreshPage()
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load item detail."),
      )
      .finally(() => setLoading(false));
  }, [numericItemId]);

  async function handleRetry(jobId: number) {
    setError(null);
    try {
      await retryJob(jobId);
      await refreshPage();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Retry failed.");
    }
  }

  async function handleQueueProcessing() {
    setError(null);
    try {
      await queueLibraryItemProcessing(numericItemId);
      await refreshPage();
    } catch (processError) {
      setError(processError instanceof Error ? processError.message : "Processing queue failed.");
    }
  }

  async function handleQueueYotoPlaylist() {
    setError(null);
    try {
      await queueYotoPlaylist(numericItemId);
      await refreshPage();
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : "Yoto playlist queue failed.");
    }
  }

  async function handleRestoreYotoPlaylistVersion(playlistId: number, versionId: number) {
    setError(null);
    try {
      await restoreYotoPlaylistVersion(playlistId, versionId);
      await refreshPage();
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Yoto playlist restore failed.");
    }
  }

  async function handleQueueArtworkPixelise() {
    setError(null);
    try {
      await queueArtworkPixelise(numericItemId);
      await refreshPage();
    } catch (artworkError) {
      setError(artworkError instanceof Error ? artworkError.message : "Artwork pixelisation queue failed.");
    }
  }

  async function handleSaveCardPlan() {
    if (!cardPlan) return;
    setError(null);
    try {
      const maxPart = Math.max(1, ...Object.values(cardPlanDraft));
      const parts = Array.from({ length: maxPart }, (_, index) => {
        const partNumber = index + 1;
        return {
          part_number: partNumber,
          title: `${detail?.item.title ?? "Card"} - Part ${partNumber}`,
          track_ids: cardPlan.parts
            .flatMap((part) => part.tracks)
            .filter((track) => (cardPlanDraft[track.track_id] || 1) === partNumber)
            .map((track) => track.track_id),
        };
      }).filter((part) => part.track_ids.length > 0);
      const saved = await saveCardPlan(numericItemId, { parts });
      setSavedCardPlan(saved);
      setCardPlanDraft(cardPlanAssignments(saved));
      await refreshPage();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Card plan save failed.");
    }
  }

  async function handleRestoreVersion(version: VersionEvent) {
    const confirmed = window.confirm(
      `Restore ${detail?.item.title ?? "this item"} to version ${version.version_number}? This will create a new version event.`,
    );
    if (!confirmed) return;

    setError(null);
    try {
      await restoreLibraryItemVersion(numericItemId, version.id);
      await refreshPage();
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Restore failed.");
    }
  }

  if (loading) {
    return (
      <section className="panel">
        <p className="eyebrow">Library</p>
        <h2>Loading item</h2>
      </section>
    );
  }

  if (!detail) {
    return (
      <section className="panel">
        <p className="eyebrow">Library</p>
        <h2>Item unavailable</h2>
        {error ? <p className="auth-error">{error}</p> : null}
        <Link className="ghost-button" to="/">
          Back to library
        </Link>
      </section>
    );
  }

  const totalDuration = detail.tracks.reduce(
    (total, track) => total + (track.duration_seconds ?? 0),
    0,
  );

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Library detail</p>
          <h2>{detail.item.title}</h2>
          <p className="muted">
            {detail.item.content_type} · {detail.item.status} · {detail.item.readiness_status}
          </p>
        </div>
        <div className="row-actions">
          <button className="ghost-button" onClick={() => void refreshPage()} type="button">
            Refresh
          </button>
          <button className="primary-button" onClick={() => void handleQueueProcessing()} type="button">
            Process audio
          </button>
          <Link className="ghost-button" to="/">
            Back
          </Link>
        </div>
      </div>

      {error ? <p className="auth-error">{error}</p> : null}

      {detail.item.media_url || detail.item.stream_url ? (
        <div className="library-player detail-player">
          <AudioPlayer
            customAdditionalControls={[]}
            customVolumeControls={[]}
            layout="horizontal-reverse"
            preload={detail.item.stream_url ? "none" : "metadata"}
            showJumpControls={false}
            src={detail.item.media_url ?? detail.item.stream_url ?? undefined}
          />
        </div>
      ) : null}

      <div className="detail-summary-grid">
        <div className="summary-tile">
          <span className="summary-label">Tracks</span>
          <strong>{detail.tracks.length}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Duration</span>
          <strong>{totalDuration ? formatDuration(totalDuration) : "Unknown"}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Split points</span>
          <strong>{detail.split_points.length}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Jobs</span>
          <strong>{jobs.length}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Versions</span>
          <strong>{versions.length}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Assets</span>
          <strong>{detail.processed_assets.length}</strong>
        </div>
      </div>

      {detail.item.readiness_detail ? (
        <div className="detail-note">
          <p className="eyebrow">Inspection</p>
          <p>{detail.item.readiness_detail}</p>
        </div>
      ) : null}

      <div className="detail-two-column">
        <div className="prep-block">
          <h3>Readiness</h3>
          {readiness ? (
            <div className="check-list">
              {readiness.checks.map((check) => (
                <div className="check-row" key={check.key}>
                  <span className={check.ok ? "check-ok" : "check-warn"}>
                    {check.ok ? "OK" : "Review"}
                  </span>
                  <div>
                    <strong>{check.label}</strong>
                    <p className="muted">{check.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No readiness checks available." />
          )}
        </div>

        <div className="prep-block">
          <h3>Playlist settings</h3>
          <p className="muted">Cover: {detail.item.cover_art_path ?? "Not set"}</p>
          <p className="muted">
            {detail.item.playlist_always_play_from_start ? "Play from start" : "Resume allowed"} ·{" "}
            {detail.item.playlist_shuffle_tracks ? "Shuffle" : "Ordered"} ·{" "}
            {detail.item.playlist_hide_track_numbers ? "Track numbers hidden" : "Track numbers shown"}
          </p>
        </div>
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Artwork</p>
            <h2>Cover assets</h2>
          </div>
          <button className="primary-button" onClick={() => void handleQueueArtworkPixelise()} type="button">
            Pixelise cover
          </button>
        </div>
        {detail.artwork_assets.length === 0 ? (
          <EmptyState message="No artwork assets recorded yet." />
        ) : (
          <div className="compact-table">
            {detail.artwork_assets.map((asset) => (
              <div className="compact-table-row" key={asset.id}>
                <span className="status-pill status-pill-muted">{asset.kind}</span>
                <div>
                  <strong>{asset.output_path ?? asset.source_path}</strong>
                  <p className="muted">
                    {asset.status} · {asset.width && asset.height ? `${asset.width}x${asset.height}` : "source"} ·{" "}
                    {asset.palette ?? "original"}
                  </p>
                </div>
                <span className="muted">{asset.checksum_sha256?.slice(0, 8) ?? "pending"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Tracks</p>
            <h2>Playlist tracks</h2>
          </div>
          <span className="status-pill">{detail.tracks.length} tracks</span>
        </div>
        {detail.tracks.length === 0 ? (
          <EmptyState message="No tracks discovered yet." />
        ) : (
          <div className="compact-table">
            {detail.tracks.map((track) => (
              <div className="compact-table-row" key={track.id}>
                <span className="status-pill status-pill-muted">#{track.track_number}</span>
                <div>
                  <strong>{track.title}</strong>
                  <p className="muted">
                    {formatDuration(track.duration_seconds)} ·{" "}
                    {track.is_stream ? "Stream" : track.track_behavior}
                    {track.source_start_seconds !== null ? ` · starts ${formatDuration(track.source_start_seconds)}` : ""}
                  </p>
                </div>
                <span className="muted">{track.icon_path ?? "No icon"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Card plan</p>
            <h2>Proposed parts</h2>
          </div>
          <span className="status-pill">
            {cardPlan ? `${cardPlan.parts.length} parts` : "No plan"}
          </span>
        </div>
        {cardPlan && cardPlan.parts.length > 0 ? (
          <div className="card-plan-list">
            <div className="row-actions">
              <button className="primary-button" onClick={() => void handleSaveCardPlan()} type="button">
                Save card plan
              </button>
              <span className="status-pill status-pill-muted">
                {savedCardPlan && savedCardPlan.parts.length > 0 ? "Saved plan available" : "Preview draft"}
              </span>
            </div>
            {cardPlan.parts.map((part) => (
              <article className="card-plan-part" key={part.part_number}>
                <div className="section-header">
                  <div>
                    <h3>{part.title}</h3>
                    <p className="muted">
                      {formatDuration(part.duration_seconds)} · {part.estimated_size_mb} MB ·{" "}
                      {part.track_count} tracks
                    </p>
                  </div>
                  <span className="status-pill status-pill-muted">Part {part.part_number}</span>
                </div>
                {part.warnings.length > 0 ? (
                  <p className="auth-error">{part.warnings.join(" ")}</p>
                ) : null}
                <div className="compact-list">
                  {part.tracks.map((track) => (
                    <label className="plan-track-row" key={track.track_id}>
                      <span>
                        #{track.track_number} {track.title} · {formatDuration(track.duration_seconds)}
                        {track.estimated_size_mb !== null ? ` · ${track.estimated_size_mb} MB` : ""}
                      </span>
                      <select
                        onChange={(event) =>
                          setCardPlanDraft((current) => ({
                            ...current,
                            [track.track_id]: Number(event.target.value),
                          }))
                        }
                        value={cardPlanDraft[track.track_id] || part.part_number}
                      >
                        {Array.from({ length: Math.max(cardPlan.parts.length + 1, 2) }, (_, index) => index + 1).map(
                          (partNumber) => (
                            <option key={partNumber} value={partNumber}>
                              Part {partNumber}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  ))}
                </div>
              </article>
            ))}
            {cardPlan.warnings.length > 0 ? (
              <p className="auth-error">{cardPlan.warnings.join(" ")}</p>
            ) : null}
          </div>
        ) : (
          <EmptyState message="No plan yet. Inspect media or add tracks first." />
        )}
        {savedCardPlan && savedCardPlan.parts.length > 0 ? (
          <div className="saved-plan-summary">
            <h3>Saved plan</h3>
            {savedCardPlan.parts.map((part) => (
              <p className="muted" key={part.part_number}>
                Part {part.part_number}: {part.track_count} tracks · {formatDuration(part.duration_seconds)}
              </p>
            ))}
          </div>
        ) : null}
      </div>

      <div className="detail-two-column">
        <div className="prep-block">
          <h3>Split points</h3>
          {detail.split_points.length === 0 ? (
            <EmptyState message="No manual split points." />
          ) : (
            <div className="compact-list">
              {detail.split_points.map((splitPoint) => (
                <p className="muted" key={splitPoint.id}>
                  {formatDuration(splitPoint.timestamp_seconds)} · {splitPoint.title}
                  {splitPoint.part_number ? ` · Part ${splitPoint.part_number}` : ""}
                </p>
              ))}
            </div>
          )}
        </div>

        <div className="prep-block">
          <h3>Related jobs</h3>
          {jobs.length === 0 ? (
            <EmptyState message="No jobs linked to this item." />
          ) : (
            <div className="compact-list">
              {jobs.map((job) => (
                <div className="job-detail-row" key={job.id}>
                  <div>
                    <strong>{job.type}</strong>
                    <p className="muted">
                      {job.status} · {job.progress_percent}% · {job.progress_message}
                    </p>
                  </div>
                  {job.status === "failed" ? (
                    <button className="ghost-button" onClick={() => void handleRetry(job.id)} type="button">
                      Retry
                    </button>
                  ) : (
                    <span className="status-pill status-pill-muted">#{job.id}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Processed</p>
            <h2>Yoto-ready assets</h2>
          </div>
          <span className="status-pill">{detail.processed_assets.length} assets</span>
        </div>
        {detail.processed_assets.length === 0 ? (
          <EmptyState message="No processed audio assets yet." />
        ) : (
          <div className="compact-table">
            {detail.processed_assets.map((asset) => (
              <div className="compact-table-row" key={asset.id}>
                <span className="status-pill status-pill-muted">{asset.profile}</span>
                <div>
                  <strong>{asset.output_path}</strong>
                  <p className="muted">
                    {asset.codec} · {asset.bitrate_kbps} kbps · {asset.channels}ch ·{" "}
                    {formatDuration(asset.duration_seconds)}
                  </p>
                </div>
                <span className="muted">{Math.round(asset.size_bytes / 1024)} KB</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Yoto</p>
            <h2>Playlist upload</h2>
          </div>
          <button className="primary-button" onClick={() => void handleQueueYotoPlaylist()} type="button">
            Queue Yoto playlist
          </button>
        </div>
        {yotoPlaylists.length === 0 ? (
          <EmptyState message="No Yoto playlist drafts queued yet." />
        ) : (
          <div className="compact-table">
            {yotoPlaylists.map((playlist) => (
              <div className="compact-table-row" key={playlist.id}>
                <span className="status-pill status-pill-muted">{playlist.status}</span>
                <div>
                  <strong>{playlist.title}</strong>
                  <p className="muted">
                    Job {playlist.related_job_id ?? "pending"} ·{" "}
                    {playlist.remote_playlist_uri ?? "Manual link pending"}
                  </p>
                  {(yotoPlaylistVersions[playlist.id] ?? []).slice(0, 3).map((version) => (
                    <p className="muted" key={version.id}>
                      Version {version.version_number}: {version.summary}
                      {version.status !== "restored" ? (
                        <button
                          className="inline-button"
                          onClick={() => void handleRestoreYotoPlaylistVersion(playlist.id, version.id)}
                          type="button"
                        >
                          Restore
                        </button>
                      ) : null}
                    </p>
                  ))}
                </div>
                <span className="muted">
                  {Array.isArray(playlist.payload.chapters) ? playlist.payload.chapters.length : 0} tracks
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">History</p>
            <h2>Version events</h2>
          </div>
          <span className="status-pill">{versions.length} events</span>
        </div>
        {versions.length === 0 ? (
          <EmptyState message="No version events recorded for this item yet." />
        ) : (
          <div className="version-list">
            {versions.map((version) => (
              <article className="version-row" key={version.id}>
                <div>
                  <h3>Version {version.version_number}</h3>
                  <p className="muted">{version.summary}</p>
                </div>
                <div className="version-actions">
                  <span className="status-pill status-pill-muted">{version.event_type}</span>
                  <button
                    className="ghost-button"
                    onClick={() => void handleRestoreVersion(version)}
                    type="button"
                  >
                    Restore
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function ImportPage({ session }: { session: SessionResponse }) {
  const [imports, setImports] = useState<ImportRequest[]>([]);
  const [sources, setSources] = useState<ImportSourceInfo | null>(null);
  const [mode, setMode] = useState<"upload" | "filesystem">("upload");
  const [form, setForm] = useState({
    title: "",
    source_path: "",
    content_type: "Audiobook",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refreshImports() {
    setImports(await fetchImports());
  }

  useEffect(() => {
    void Promise.all([refreshImports(), fetchImportSources().then(setSources)]).catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load imports."),
    );
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "upload") {
        if (!selectedFile) {
          throw new Error("Choose a media file to upload.");
        }
        await uploadImport({
          title: form.title,
          content_type: form.content_type,
          requested_by_user_slug: session.user.slug,
          media_file: selectedFile,
        });
      } else {
        await createImport({
          title: form.title,
          source_type: "filesystem",
          source_path: form.source_path || null,
          content_type: form.content_type,
          requested_by_user_slug: session.user.slug,
        });
      }
      setForm({ title: "", source_path: "", content_type: "Audiobook" });
      setSelectedFile(null);
      await refreshImports();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Import failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleHideImport(importId: number) {
    setError(null);
    try {
      await hideImport(importId);
      await refreshImports();
    } catch (hideError) {
      setError(hideError instanceof Error ? hideError.message : "Hide failed.");
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Import</p>
          <h2>Add media</h2>
        </div>
        <span className="status-pill">{imports.length} imports</span>
      </div>

      <div className="segmented-control" aria-label="Import source">
        <button
          className={mode === "upload" ? "segment-active" : ""}
          onClick={() => setMode("upload")}
          type="button"
        >
          Upload
        </button>
        <button
          className={mode === "filesystem" ? "segment-active" : ""}
          onClick={() => setMode("filesystem")}
          type="button"
        >
          Filesystem
        </button>
      </div>

      <form className="import-form" onSubmit={(event) => void handleSubmit(event)}>
        <div className="import-grid">
          <label>
            Title
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, title: event.target.value }))
              }
              required
              value={form.title}
            />
          </label>
          <label>
            Content type
            <select
              onChange={(event) =>
                setForm((current) => ({ ...current, content_type: event.target.value }))
              }
              value={form.content_type}
            >
              {contentTypes.map((contentType) => (
                <option key={contentType}>{contentType}</option>
              ))}
            </select>
          </label>
        </div>

        {mode === "upload" ? (
          <div className="drop-panel">
            <label className="file-picker">
              <span>{selectedFile ? selectedFile.name : "Choose media file"}</span>
              <input
                accept={sources?.allowed_extensions.join(",")}
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <p className="muted">
              Uploads are staged in{" "}
              {sources?.browser_upload_path ?? "/var/lib/yotowebmgr/media/imports/uploads"}.
            </p>
          </div>
        ) : (
          <div className="drop-panel">
            <label>
              Source path
              <input
                onChange={(event) =>
                  setForm((current) => ({ ...current, source_path: event.target.value }))
                }
                placeholder={`${
                  sources?.filesystem_drop_path ?? "/var/lib/yotowebmgr/media/imports/drop"
                }/example.m4b`}
                value={form.source_path}
              />
            </label>
            <p className="muted">
              Filesystem imports are limited to{" "}
              {sources?.filesystem_drop_path ?? "/var/lib/yotowebmgr/media/imports/drop"}.
            </p>
          </div>
        )}

        <div className="form-actions">
          <span className="muted">Queued as {session.user.display_name}</span>
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Queueing" : "Queue import"}
          </button>
        </div>
      </form>
      {error ? <p className="auth-error">{error}</p> : null}

      <h3 className="subsection-title">Recent imports</h3>
      <div className="item-list">
        {imports.length === 0 ? (
          <EmptyState message="No imports queued yet." />
        ) : (
          imports.map((item) => (
            <article className="list-row" key={item.id}>
              <div>
                <h3>{item.title}</h3>
                <p className="muted">
                  {item.source_type} · {item.content_type} · {item.status}
                </p>
              </div>
              <div className="row-actions">
                <span className="status-pill status-pill-muted">
                  Job {item.related_job_id ?? "pending"}
                </span>
                <button
                  aria-label={`Hide ${item.title}`}
                  className="danger-icon-button"
                  onClick={() => void handleHideImport(item.id)}
                  title="Hide and mark ready for deletion"
                  type="button"
                >
                  x
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refreshJobs() {
    setJobs(await fetchJobs());
  }

  useEffect(() => {
    void refreshJobs().catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load jobs."),
    );
  }, []);

  async function handleRetry(jobId: number) {
    setError(null);
    try {
      await retryJob(jobId);
      await refreshJobs();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Retry failed.");
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Jobs</p>
          <h2>Background work</h2>
        </div>
        <button className="ghost-button" onClick={() => void refreshJobs()} type="button">
          Refresh
        </button>
      </div>
      {error ? <p className="auth-error">{error}</p> : null}
      {jobs.length === 0 ? (
        <EmptyState message="No jobs yet." />
      ) : (
        <div className="item-list">
          {jobs.map((job) => (
            <article className="list-row" key={job.id}>
              <div>
                <h3>{job.type}</h3>
                <p className="muted">
                  {job.status} · {job.progress_percent}% · {job.progress_message}
                </p>
              </div>
              {job.status === "failed" ? (
                <button className="ghost-button" onClick={() => void handleRetry(job.id)} type="button">
                  Retry
                </button>
              ) : (
                <span className="status-pill status-pill-muted">#{job.id}</span>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [form, setForm] = useState({ name: "", color: "#90cdf4" });
  const [error, setError] = useState<string | null>(null);

  async function refreshTags() {
    setTags(await fetchTags());
  }

  useEffect(() => {
    void refreshTags().catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load tags."),
    );
  }, []);

  async function handleCreateTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await createTag({ name: form.name, color: form.color || null });
      setForm({ name: "", color: "#90cdf4" });
      await refreshTags();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create tag.");
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Tags</p>
          <h2>Reusable tags</h2>
        </div>
        <span className="status-pill">{tags.length} tags</span>
      </div>
      {error ? <p className="auth-error">{error}</p> : null}
      <form className="import-form" onSubmit={(event) => void handleCreateTag(event)}>
        <div className="import-grid">
          <label>
            Name
            <input
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              required
              value={form.name}
            />
          </label>
          <label>
            Color
            <input
              onChange={(event) => setForm((current) => ({ ...current, color: event.target.value }))}
              type="color"
              value={form.color}
            />
          </label>
          <button className="primary-button" type="submit">
            Create tag
          </button>
        </div>
      </form>
      {tags.length === 0 ? (
        <EmptyState message="No tags yet." />
      ) : (
        <div className="tag-grid">
          {tags.map((tag) => (
            <article className="tag-row" key={tag.id}>
              <span className="tag-chip" style={{ borderColor: tag.color ?? undefined }}>
                {tag.name}
              </span>
              <span className="muted">{tag.usage_count} uses</span>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function CardsPage() {
  const [cards, setCards] = useState<PhysicalCard[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    card_code: "",
    programmable_id: "",
    display_name: "",
    card_kind: "generic_mifare_ultralight_ev1",
    nfc_technology: "NFC Type 2",
    chip_type: "MIFARE Ultralight EV1",
    memory_size_bytes: "48",
    ndef_prepared: true,
    ndef_format_command: defaultNdefFormatCommand,
    programming_app: "NFC Tools",
    source_card_code: "",
    is_reusable_transfer_card: false,
    ready_to_link_in_app: false,
    linked_manually: false,
    overwrite_ok: false,
    downloaded_to_player_confirmed: false,
    needs_player_download: false,
    yoto_playlist_uri: "",
    status: "available",
    label_color: "",
    tested: false,
    notes: "",
  });

  async function refreshCards() {
    setCards(await fetchCards());
  }

  useEffect(() => {
    void refreshCards().catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load cards."),
    );
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createCard({
        card_code: form.card_code,
        programmable_id: form.programmable_id || null,
        display_name: form.display_name,
        card_kind: form.card_kind,
        nfc_technology: form.nfc_technology || null,
        chip_type: form.chip_type || null,
        memory_size_bytes: form.memory_size_bytes ? Number(form.memory_size_bytes) : null,
        ndef_prepared: form.ndef_prepared,
        ndef_format_command: form.ndef_format_command || null,
        programming_app: form.programming_app || null,
        source_card_code: form.source_card_code || null,
        is_reusable_transfer_card: form.is_reusable_transfer_card,
        ready_to_link_in_app: form.ready_to_link_in_app,
        linked_manually: form.linked_manually,
        overwrite_ok: form.overwrite_ok,
        downloaded_to_player_confirmed: form.downloaded_to_player_confirmed,
        needs_player_download: form.needs_player_download,
        yoto_playlist_uri: form.yoto_playlist_uri || null,
        status: form.status,
        label_color: form.label_color || null,
        tested: form.tested,
        notes: form.notes || null,
      });
      setForm((current) => ({
        ...current,
        card_code: "",
        programmable_id: "",
        display_name: "",
        source_card_code: "",
        yoto_playlist_uri: "",
        label_color: "",
        tested: false,
        ready_to_link_in_app: false,
        linked_manually: false,
        overwrite_ok: false,
        downloaded_to_player_confirmed: false,
        needs_player_download: false,
        notes: "",
      }));
      await refreshCards();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Card creation failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Cards</p>
          <h2>Card inventory</h2>
        </div>
        <span className="status-pill">{cards.length} cards</span>
      </div>

      <form className="import-form" onSubmit={(event) => void handleSubmit(event)}>
        <div className="import-grid import-grid-wide">
          <label>
            Card ID
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, card_code: event.target.value.toUpperCase() }))
              }
              pattern="[A-Za-z0-9]+"
              placeholder="CARD01"
              required
              value={form.card_code}
            />
          </label>
          <label>
            Programmable ID
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, programmable_id: event.target.value }))
              }
              placeholder="04A1B2C3D4"
              value={form.programmable_id}
            />
          </label>
          <label>
            Name
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, display_name: event.target.value }))
              }
              placeholder="Card 01"
              required
              value={form.display_name}
            />
          </label>
        </div>

        <div className="import-grid import-grid-wide">
          <label>
            Kind
            <select
              onChange={(event) =>
                setForm((current) => ({ ...current, card_kind: event.target.value }))
              }
              value={form.card_kind}
            >
              <option value="official_myo">Official MYO</option>
              <option value="generic_mifare_ultralight_ev1">Generic MIFARE Ultralight EV1</option>
              <option value="other_nfc">Other NFC</option>
            </select>
          </label>
          <label>
            NFC technology
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, nfc_technology: event.target.value }))
              }
              value={form.nfc_technology}
            />
          </label>
        </div>

        <div className="import-grid import-grid-wide">
          <label>
            Chip
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, chip_type: event.target.value }))
              }
              value={form.chip_type}
            />
          </label>
          <label>
            Memory bytes
            <input
              min="1"
              onChange={(event) =>
                setForm((current) => ({ ...current, memory_size_bytes: event.target.value }))
              }
              type="number"
              value={form.memory_size_bytes}
            />
          </label>
          <label>
            Programming app
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, programming_app: event.target.value }))
              }
              value={form.programming_app}
            />
          </label>
        </div>

        <div className="import-grid import-grid-wide">
          <label>
            Source card
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, source_card_code: event.target.value.toUpperCase() }))
              }
              placeholder="MYOTRANSFER01"
              value={form.source_card_code}
            />
          </label>
          <label>
            Playlist URI
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, yoto_playlist_uri: event.target.value }))
              }
              placeholder="yoto://playlist/..."
              value={form.yoto_playlist_uri}
            />
          </label>
          <label>
            Status
            <select
              onChange={(event) =>
                setForm((current) => ({ ...current, status: event.target.value }))
              }
              value={form.status}
            >
              <option value="available">Available</option>
              <option value="ready_to_link">Ready to link</option>
              <option value="linked">Linked</option>
              <option value="needs_attention">Needs attention</option>
            </select>
          </label>
        </div>

        <div className="import-grid">
          <label>
            NDEF command
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, ndef_format_command: event.target.value }))
              }
              value={form.ndef_format_command}
            />
          </label>
          <label>
            Label colour
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, label_color: event.target.value }))
              }
              value={form.label_color}
            />
          </label>
          <label>
            Notes
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, notes: event.target.value }))
              }
              value={form.notes}
            />
          </label>
        </div>

        <div className="checkbox-pair">
          <label className="checkbox-row">
            <input
              checked={form.ndef_prepared}
              onChange={(event) =>
                setForm((current) => ({ ...current, ndef_prepared: event.target.checked }))
              }
              type="checkbox"
            />
            NDEF prepared
          </label>
          <label className="checkbox-row">
            <input
              checked={form.tested}
              onChange={(event) =>
                setForm((current) => ({ ...current, tested: event.target.checked }))
              }
              type="checkbox"
            />
            Tested
          </label>
          <label className="checkbox-row">
            <input
              checked={form.is_reusable_transfer_card}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  is_reusable_transfer_card: event.target.checked,
                }))
              }
              type="checkbox"
            />
            Reusable transfer card
          </label>
          <label className="checkbox-row">
            <input
              checked={form.ready_to_link_in_app}
              onChange={(event) =>
                setForm((current) => ({ ...current, ready_to_link_in_app: event.target.checked }))
              }
              type="checkbox"
            />
            Ready to link in app
          </label>
          <label className="checkbox-row">
            <input
              checked={form.linked_manually}
              onChange={(event) =>
                setForm((current) => ({ ...current, linked_manually: event.target.checked }))
              }
              type="checkbox"
            />
            Linked manually
          </label>
          <label className="checkbox-row">
            <input
              checked={form.overwrite_ok}
              onChange={(event) =>
                setForm((current) => ({ ...current, overwrite_ok: event.target.checked }))
              }
              type="checkbox"
            />
            OK to overwrite
          </label>
          <label className="checkbox-row">
            <input
              checked={form.needs_player_download}
              onChange={(event) =>
                setForm((current) => ({ ...current, needs_player_download: event.target.checked }))
              }
              type="checkbox"
            />
            Needs player download
          </label>
          <label className="checkbox-row">
            <input
              checked={form.downloaded_to_player_confirmed}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  downloaded_to_player_confirmed: event.target.checked,
                }))
              }
              type="checkbox"
            />
            Download confirmed
          </label>
        </div>

        <div className="form-actions">
          <span className="muted">Alphanumeric card IDs only</span>
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Adding" : "Add card"}
          </button>
        </div>
      </form>
      {error ? <p className="auth-error">{error}</p> : null}

      <div className="item-list">
        {cards.length === 0 ? (
          <EmptyState message="No cards yet." />
        ) : (
          cards.map((card) => (
            <article className="list-row" key={card.id}>
              <div>
                <h3>{card.display_name}</h3>
                <p className="muted">
                  {card.card_code} · {card.card_kind} · {card.status}
                </p>
                <p className="muted">
                  {card.programmable_id ?? "No programmable ID"} ·{" "}
                  {card.chip_type ?? "Chip unknown"} ·{" "}
                  {card.memory_size_bytes ? `${card.memory_size_bytes} bytes` : "Memory unknown"}
                </p>
              </div>
              <div className="row-actions">
                {card.ndef_prepared ? <span className="status-pill">NDEF</span> : null}
                {card.ready_to_link_in_app ? <span className="status-pill">Ready</span> : null}
                {card.linked_manually ? <span className="status-pill">Linked</span> : null}
                {card.needs_player_download ? (
                  <span className="status-pill status-pill-muted">Needs download</span>
                ) : null}
                {card.tested ? <span className="status-pill status-pill-muted">Tested</span> : null}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [yotoCredential, setYotoCredential] = useState<YotoCredentialStatus | null>(null);
  const [yotoAccountLabel, setYotoAccountLabel] = useState("Household Yoto");
  const [preparedAuthUrl, setPreparedAuthUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void Promise.all([fetchSettings(), fetchYotoCredentialStatus()])
      .then(([nextSettings, nextCredential]) => {
        setSettings(nextSettings);
        setYotoCredential(nextCredential);
        setYotoAccountLabel(nextCredential.account_label);
        setPreparedAuthUrl(nextCredential.authorization_url);
      })
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load settings."),
      );
  }, []);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      setSettings(await updateSettings(settings));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePrepareYotoOAuth() {
    setSaving(true);
    setError(null);
    try {
      const result = await startYotoOAuth(yotoAccountLabel);
      setYotoCredential(result.credential);
      setPreparedAuthUrl(result.authorization_url);
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Failed to prepare Yoto OAuth.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnectYoto() {
    setSaving(true);
    setError(null);
    try {
      const result = await disconnectYotoCredentials();
      setYotoCredential(result);
      setPreparedAuthUrl(null);
    } catch (disconnectError) {
      setError(disconnectError instanceof Error ? disconnectError.message : "Failed to disconnect Yoto.");
    } finally {
      setSaving(false);
    }
  }

  if (!settings) {
    return (
      <section className="panel">
        <p className="eyebrow">Settings</p>
        <h2>Processing defaults</h2>
        {error ? (
          <p className="auth-error">{error}</p>
        ) : (
          <EmptyState message="Loading settings..." />
        )}
      </section>
    );
  }

  return (
    <section className="panel">
      <p className="eyebrow">Settings</p>
      <h2>Processing defaults</h2>
      <form className="data-form" onSubmit={(event) => void handleSave(event)}>
        <label>
          Target duration hours
          <input
            min="0"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, target_duration_hours: Number(event.target.value) } : current,
              )
            }
            step="0.1"
            type="number"
            value={settings.target_duration_hours}
          />
        </label>
        <label>
          Target size MB
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, target_size_mb: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.target_size_mb}
          />
        </label>
        <label>
          Audiobook bitrate kbps
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, audiobook_bitrate_kbps: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.audiobook_bitrate_kbps}
          />
        </label>
        <label>
          Music bitrate kbps
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, music_bitrate_kbps: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.music_bitrate_kbps}
          />
        </label>
        <label className="checkbox-row">
          <input
            checked={settings.normalise_loudness_default}
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, normalise_loudness_default: event.target.checked }
                  : current,
              )
            }
            type="checkbox"
          />
          Normalise loudness by default
        </label>

        <h3 className="settings-section-title">Yoto API</h3>
        <label className="checkbox-row">
          <input
            checked={settings.yoto_api_enabled}
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_api_enabled: event.target.checked } : current,
              )
            }
            type="checkbox"
          />
          Enable Yoto API integration
        </label>
        <label>
          API base URL
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_api_base_url: event.target.value } : current,
              )
            }
            type="url"
            value={settings.yoto_api_base_url}
          />
        </label>
        <label>
          Auth base URL
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_auth_base_url: event.target.value } : current,
              )
            }
            type="url"
            value={settings.yoto_auth_base_url}
          />
        </label>
        <label>
          Client ID
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_client_id: event.target.value } : current,
              )
            }
            value={settings.yoto_client_id}
          />
        </label>
        <label>
          Redirect URI
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_redirect_uri: event.target.value } : current,
              )
            }
            value={settings.yoto_redirect_uri}
          />
        </label>
        <label>
          OAuth scope
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_oauth_scope: event.target.value } : current,
              )
            }
            value={settings.yoto_oauth_scope}
          />
        </label>
        <label>
          Upload timeout seconds
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, yoto_upload_timeout_seconds: Number(event.target.value) }
                  : current,
              )
            }
            type="number"
            value={settings.yoto_upload_timeout_seconds}
          />
        </label>
        <label>
          Transcode poll seconds
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, yoto_transcode_poll_seconds: Number(event.target.value) }
                  : current,
              )
            }
            type="number"
            value={settings.yoto_transcode_poll_seconds}
          />
        </label>
        <label>
          Transcode timeout minutes
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, yoto_transcode_timeout_minutes: Number(event.target.value) }
                  : current,
              )
            }
            type="number"
            value={settings.yoto_transcode_timeout_minutes}
          />
        </label>
        <p className="settings-note">
          Store refresh tokens and client secrets in Kubernetes Secrets, not application settings.
        </p>
        <div className="settings-connection-panel">
          <div>
            <h3 className="settings-section-title">Yoto connection</h3>
            <p className="settings-note">
              Status: {yotoCredential?.status ?? "loading"} · Live API call: no
            </p>
          </div>
          <label>
            Account label
            <input
              onChange={(event) => setYotoAccountLabel(event.target.value)}
              value={yotoAccountLabel}
            />
          </label>
          <div className="button-row">
            <button
              className="secondary-button"
              disabled={saving}
              onClick={() => void handlePrepareYotoOAuth()}
              type="button"
            >
              Prepare auth link
            </button>
            <button
              className="secondary-button"
              disabled={saving || !yotoCredential?.id}
              onClick={() => void handleDisconnectYoto()}
              type="button"
            >
              Disconnect locally
            </button>
          </div>
          {preparedAuthUrl ? (
            <p className="settings-note auth-url-break">
              Auth URL: <a href={preparedAuthUrl}>{preparedAuthUrl}</a>
            </p>
          ) : (
            <p className="settings-note">
              Set the client ID and redirect URI, save settings, then prepare an auth link.
            </p>
          )}
          {yotoCredential?.error_summary ? (
            <p className="settings-note">{yotoCredential.error_summary}</p>
          ) : null}
        </div>
        <button className="primary-button" disabled={saving} type="submit">
          Save settings
        </button>
      </form>
      {error ? <p className="auth-error">{error}</p> : null}
    </section>
  );
}

function AuthGate({
  session,
  onSessionChange,
}: {
  session: SessionResponse | null;
  onSessionChange: (session: SessionResponse | null) => void;
}) {
  const [authOptions, setAuthOptions] = useState<AuthProvidersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [passwordForm, setPasswordForm] = useState({ username: "", password: "" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadAuthOptions() {
      try {
        const options = await fetchAuthProviders();
        if (!cancelled) {
          setAuthOptions(options);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load auth options.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadAuthOptions();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleQuickSelect(userSlug: string) {
    setSubmitting(true);
    setError(null);
    try {
      const nextSession = await quickSelectUser(userSlug);
      onSessionChange(nextSession);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const nextSession = await loginWithPassword(passwordForm.username, passwordForm.password);
      onSessionChange(nextSession);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (session) {
    return (
      <section className="auth-panel">
        <div className="auth-panel-header">
          <div>
            <p className="eyebrow">Signed in</p>
            <h2>{session.user.display_name}</h2>
          </div>
          <button className="ghost-button" onClick={() => onSessionChange(null)} type="button">
            Switch user
          </button>
        </div>
        <p className="auth-status">
          Signed in with <strong>{session.user.auth_method}</strong>. {session.message}
        </p>
      </section>
    );
  }

  return (
    <section className="auth-panel">
      <p className="eyebrow">Authentication</p>
      <h2>Select a household user</h2>
      <p className="auth-copy">
        Start simple for now: choose Krystin or Dale from the home page. Password auth and OAuth
        remain scaffolded behind the same API shape so they can replace this flow cleanly later.
      </p>

      {loading ? <p className="auth-status">Loading auth options...</p> : null}
      {error ? <p className="auth-error">{error}</p> : null}

      <div className="user-grid">
        {authOptions?.users.map((user) => (
          <button
            key={user.slug}
            className="user-card"
            disabled={!user.can_quick_select || submitting}
            onClick={() => void handleQuickSelect(user.slug)}
            type="button"
          >
            <span className="user-name">{user.display_name}</span>
            <span className="user-meta">@{user.username}</span>
            <span className="user-meta">
              {user.has_password ? "Password configured" : "Quick select only"}
            </span>
          </button>
        ))}
      </div>

      <form className="password-form" onSubmit={(event) => void handlePasswordSubmit(event)}>
        <div className="auth-panel-header">
          <div>
            <p className="eyebrow">Scaffolded</p>
            <h3>Password sign-in</h3>
          </div>
          <span className="status-pill">
            {authOptions?.providers.find((provider) => provider.key === "password")?.configured
              ? "Ready"
              : "Not configured"}
          </span>
        </div>
        <label>
          Username
          <input
            autoComplete="username"
            onChange={(event) =>
              setPasswordForm((current) => ({ ...current, username: event.target.value }))
            }
            value={passwordForm.username}
          />
        </label>
        <label>
          Password
          <input
            autoComplete="current-password"
            onChange={(event) =>
              setPasswordForm((current) => ({ ...current, password: event.target.value }))
            }
            type="password"
            value={passwordForm.password}
          />
        </label>
        <button className="primary-button" disabled={submitting} type="submit">
          Sign in with password
        </button>
      </form>

      <div className="oauth-strip">
        <span className="status-pill status-pill-muted">Future</span>
        <p>OAuth 2.0 provider support is reserved in the backend contract and can be enabled later.</p>
      </div>
    </section>
  );
}

export default function App() {
  const [session, setSession] = useState<SessionResponse | null>(() => {
    const stored = window.localStorage.getItem(sessionStorageKey);
    return stored ? (JSON.parse(stored) as SessionResponse) : null;
  });

  useEffect(() => {
    if (session) {
      window.localStorage.setItem(sessionStorageKey, JSON.stringify(session));
      return;
    }
    window.localStorage.removeItem(sessionStorageKey);
  }, [session]);

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="eyebrow">YotoWebMgr</p>
        <h1>Household audio management for Yoto MYO cards.</h1>
        <p className="hero-copy">
          Import preserved originals, prepare Yoto-ready media, plan cards, and track playlist
          history from one place.
        </p>
      </header>

      <AuthGate onSessionChange={setSession} session={session} />

      {session ? (
        <nav className="nav-grid" aria-label="Primary">
          {sections.map((section) => {
            const path = section === "Library" ? "/" : `/${section.toLowerCase()}`;
            return (
              <NavLink
                key={section}
                to={path}
                className={({ isActive }) => `nav-card${isActive ? " nav-card-active" : ""}`}
              >
                {section}
              </NavLink>
            );
          })}
        </nav>
      ) : null}

      <main>
        <Routes>
          <Route
            path="/"
            element={session ? <LibraryPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/library/:itemId"
            element={session ? <LibraryDetailPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/import"
            element={
              session ? <ImportPage session={session} /> : <PlaceholderPage title="Home" />
            }
          />
          <Route
            path="/cards"
            element={session ? <CardsPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/jobs"
            element={session ? <JobsPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/tags"
            element={session ? <TagsPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/settings"
            element={session ? <SettingsPage /> : <PlaceholderPage title="Home" />}
          />
        </Routes>
      </main>
    </div>
  );
}
