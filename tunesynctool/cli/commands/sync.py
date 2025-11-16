from typing import Optional, List

from tunesynctool.cli.utils.driver import get_driver_by_name, SUPPORTED_PROVIDERS
from tunesynctool.drivers import ServiceDriver
from tunesynctool.features import PlaylistSynchronizer, TrackMatcher
from tunesynctool.models import Track
from tunesynctool.exceptions import PlaylistNotFoundException, UnsupportedFeatureException

from click import command, option, Choice, echo, argument, pass_obj, UsageError, style, Abort
from tqdm import tqdm

COMMON_MATCH_ISSUE_REASON = 'This is likely caused by tracks not being available on the target service, they lack metadata or the matching algorithm was unsuccessful in finding them.'

def list_tracks(tracks: List[Track], color: str = 'yellow') -> None:
    for track in tracks:
        echo(style(track, fg=color))

@command()
@pass_obj
@option('--from', 'from_provider', type=Choice(SUPPORTED_PROVIDERS), required=True, help='The provider to sync the playlist from.')
@option('--from-playlist', 'from_playlist_id', type=str, required=True, help='ID of the playlist on the source provider you want to sync from.')
@option('--to', 'to_provider', type=Choice(SUPPORTED_PROVIDERS), required=True, help='The target provider to sync the playlist to.')
@option('--to-playlist', 'to_playlist_id', type=str, required=True, help='ID of the playlist on the target provider you want to sync to.')
@option('--preview', 'is_preview', is_flag=True, show_default=True, default=False, help='Preview the sync without actually touching the target service.')
@option('--diff', 'show_diff', is_flag=True, show_default=True, default=False, help='Show the difference between the source and target playlists.')
@option('--misses', 'show_misses', is_flag=True, show_default=True, default=False, help='Show the tracks that couldn\'t be matched.')
@option('--limit', 'limit', type=int, default=0, show_default=True, help='Limit the number of tracks to transfer. 0 or smaller means no limit. Default is 100. There is no upper limit, but be aware that some services may rate limit you.')
def sync(
    ctx: Optional[dict],
    from_provider: str,
    from_playlist_id: str,
    to_provider: str,
    to_playlist_id: str,
    is_preview: bool,
    show_diff: bool,
    show_misses: bool,
    limit: int
    ):
    """Synchronizes a playlist from one service to another. Updates the target playlist with the source playlist's missing tracks."""

    try:
        source_driver: ServiceDriver = get_driver_by_name(from_provider)(ctx['config'])
        target_driver: ServiceDriver = get_driver_by_name(to_provider)(ctx['config'])
    except ValueError as e:
        raise UsageError(e)
    
    echo(style('Looking up playlists...', fg='blue'))
    
    try:
        source_playlist = source_driver.get_playlist(from_playlist_id)
        target_playlist = target_driver.get_playlist(to_playlist_id)
        echo(style(f"Found source playlist \"{target_playlist}\" and target playlist \"{source_playlist}\"", fg='blue'))
    except PlaylistNotFoundException:
        raise UsageError('One or more playlist IDs are invalid.')

    source_playlist_tracks = source_driver.get_playlist_tracks(
        playlist_id=from_playlist_id,
        limit=limit
    )
    target_playlist_tracks = target_driver.get_playlist_tracks(
        playlist_id=to_playlist_id,
        limit=0,
    )

    synchronizer = PlaylistSynchronizer(
        source_driver=source_driver,
        target_driver=target_driver
    )

    tracks_to_add = synchronizer.find_missing_tracks(
        source_playlist_tracks=source_playlist_tracks,
        target_playlist_tracks=target_playlist_tracks
    )

    tracks_to_remove: List[Track] = []
    skipping_removals_due_to_limit = limit > 0
    if not skipping_removals_due_to_limit:
        tracks_to_remove = synchronizer.find_tracks_to_remove(
            source_playlist_tracks=source_playlist_tracks,
            target_playlist_tracks=target_playlist_tracks
        )

    echo(style(f'Found {len(tracks_to_add)} tracks that are missing from the target playlist', fg='blue'))
    if skipping_removals_due_to_limit:
        echo(style('Skipping removal checks because --limit was provided. Extra tracks will remain untouched.', fg='yellow'))
    else:
        echo(style(f'Found {len(tracks_to_remove)} tracks that only exist on the target playlist', fg='blue'))

    # Check if order needs to be fixed even when track sets match
    order_needs_sync = False
    if len(tracks_to_add) == 0 and len(tracks_to_remove) == 0 and len(source_playlist_tracks) == len(target_playlist_tracks):
        # Compare order by checking if matched tracks are in same positions
        for i, source_track in enumerate(source_playlist_tracks):
            if i >= len(target_playlist_tracks):
                break
            target_track = target_playlist_tracks[i]
            # Use same matching logic as find_missing_tracks
            if not source_track.matches(target_track):
                from tunesynctool.utilities import clean_str, extract_core_title, calculate_str_similarity
                source_core = clean_str(extract_core_title(source_track.title))
                target_core = clean_str(extract_core_title(target_track.title))
                source_artist = clean_str(source_track.primary_artist)
                target_artist = clean_str(target_track.primary_artist)
                
                title_sim = calculate_str_similarity(source_core, target_core)
                artist_sim = calculate_str_similarity(source_artist, target_artist)
                
                if artist_sim < 0.5:
                    source_words = set(source_artist.split())
                    target_words = set(target_artist.split())
                    if source_words & target_words:
                        artist_sim = 0.7
                
                if not (title_sim >= 0.85 and artist_sim >= 0.5):
                    order_needs_sync = True
                    break

    if len(tracks_to_add) == 0 and len(tracks_to_remove) == 0 and not order_needs_sync:
        echo(style('No tracks to sync, target playlist is up-to-date', fg='green'))
        return
    
    if order_needs_sync:
        echo(style('Track order differs from source - will reorder playlist', fg='blue'))

    if show_diff and len(tracks_to_add) > 0:
        echo(style('Tracks to add:', fg='yellow'))
        list_tracks(tracks_to_add, color='yellow')

    if show_diff and len(tracks_to_remove) > 0:
        echo(style('Tracks to remove:', fg='magenta'))
        list_tracks(tracks_to_remove, color='magenta')
    
    matcher = TrackMatcher(target_driver)

    matched_tracks: List[Track] = []
    unmatched_tracks: List[Track] = []

    if len(tracks_to_add) > 0:
        for track in tqdm(tracks_to_add, desc='Matching tracks'):
            matched_track = matcher.find_match(track)

            if matched_track:
                matched_tracks.append(matched_track)
                tqdm.write(style(f"Success: Found match: \"{track}\" --> \"{matched_track}\"", fg='green'))
            else:
                unmatched_tracks.append(track)
                tqdm.write(style(f"Fail: No result for \"{track}\"", fg='yellow'))

        echo(style(f"Found {len(matched_tracks)} matches in total", fg='blue' if len(matched_tracks) > 0 else 'red'))

        if len(matched_tracks) > 0:
            echo(style("Updating target playlist with missing tracks...", fg='blue'))

            if is_preview:
                echo(style("Preview mode is enabled, skipping actual additions", fg='blue'))
            else:
                try:
                    target_driver.add_tracks_to_playlist(
                        playlist_id=to_playlist_id,
                        track_ids=[track.service_id for track in matched_tracks],
                    )
                    echo(style("Target playlist updated", fg='green'))
                except Exception as e:
                    echo(style(f"Failed to transfer playlist: {e}", fg='red'))
                    raise Abort()
        else:
            echo(style("Warning: Can't add missing tracks because no matches were found.", fg='yellow'))
            echo(style(COMMON_MATCH_ISSUE_REASON, fg='yellow'))

    removal_performed = False
    if len(tracks_to_remove) > 0:
        echo(style("Removing tracks that no longer exist on the source playlist...", fg='blue'))

        if is_preview:
            echo(style("Preview mode is enabled, skipping removals", fg='blue'))
        else:
            try:
                target_driver.remove_tracks_from_playlist(
                    playlist_id=to_playlist_id,
                    track_ids=[track.service_id for track in tracks_to_remove]
                )
                removal_performed = True
                echo(style("Target playlist cleaned up", fg='green'))
            except UnsupportedFeatureException:
                echo(style('Target service does not support removing tracks via the API. Skipping removal step.', fg='yellow'))
            except Exception as e:
                echo(style(f"Failed to remove tracks: {e}", fg='red'))
                raise Abort()

    if len(unmatched_tracks) > 0:
        echo(style(f"Warning: Only {len(matched_tracks)} out of {len(tracks_to_add)} tracks were matched (the rest couldn't be identified)", fg='yellow'))
        echo(style(COMMON_MATCH_ISSUE_REASON, fg='yellow'))

        if show_misses:
            list_tracks(unmatched_tracks, color='yellow')
        else:
            echo(style('Re-run this command with the --misses flag to automatically list the missing tracks.', fg='yellow'))

    overall_success = (
        (len(tracks_to_add) == 0 or len(unmatched_tracks) == 0)
        and (len(tracks_to_remove) == 0 or removal_performed or is_preview)
    )

    # Reorder playlist if needed (when tracks match but order differs)
    if order_needs_sync and not is_preview:
        echo(style("Reordering playlist to match source order...", fg='blue'))
        try:
            synchronizer.sync(
                source_playlist_id=from_playlist_id,
                target_playlist_id=to_playlist_id
            )
            echo(style("Playlist reordered", fg='green'))
        except Exception as e:
            echo(style(f"Failed to reorder playlist: {e}", fg='red'))
            overall_success = False

    if overall_success:
        echo(style(f"Sync complete!", fg='green'))
    else:
        echo(style('Sync was only partially successful', fg='yellow'))