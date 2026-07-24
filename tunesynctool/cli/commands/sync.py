from typing import List, Optional

from tunesynctool.cli.utils.driver import (
    SOURCE_ONLY_PROVIDERS,
    SUPPORTED_PROVIDERS,
    UNSAFE_SYNC_SOURCE_PROVIDERS,
    get_driver_by_name,
)
from tunesynctool.drivers import ServiceDriver
from tunesynctool.exceptions import (
    OptionalDependencyException,
    PlaylistNotFoundException,
    ServiceDriverException,
    UnsupportedFeatureException,
)
from tunesynctool.features import PlaylistSynchronizer
from tunesynctool.models import MatchPolicy, Track

from click import Abort, Choice, UsageError, command, echo, option, pass_obj, style

COMMON_MATCH_ISSUE_REASON = 'This is likely caused by tracks not being available on the target service, they lack metadata or the matching algorithm was unsuccessful in finding them.'
MATCH_POLICIES = [policy.value for policy in MatchPolicy]

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
@option('--limit', 'limit', type=int, default=0, show_default=True, help='Limit the number of source tracks to consider. 0 or smaller means no limit. A positive limit performs additions only and leaves extra target tracks untouched.')
@option(
    '--match-policy',
    type=Choice(MATCH_POLICIES),
    default=MatchPolicy.STRICT.value,
    show_default=True,
    help='Use strict recording matching or opt into relaxed matching.',
)
def sync(
    ctx: Optional[dict],
    from_provider: str,
    from_playlist_id: str,
    to_provider: str,
    to_playlist_id: str,
    is_preview: bool,
    show_diff: bool,
    show_misses: bool,
    limit: int,
    match_policy: str,
    ):
    """Synchronize a target playlist with a source playlist and its order."""

    if to_provider in SOURCE_ONLY_PROVIDERS:
        raise UsageError(
            f"'{to_provider}' is read-only and can only be used as --from."
        )
    if from_provider in UNSAFE_SYNC_SOURCE_PROVIDERS:
        raise UsageError(
            f"'{from_provider}' cannot be used with sync because its public "
            "playlist snapshot is best-effort. Use transfer instead."
        )

    try:
        source_driver: ServiceDriver = get_driver_by_name(from_provider)(ctx['config'])
        target_driver: ServiceDriver = get_driver_by_name(to_provider)(ctx['config'])
    except (OptionalDependencyException, ValueError) as e:
        raise UsageError(str(e)) from e
    
    echo(style('Looking up playlists...', fg='blue'))
    
    try:
        source_playlist = source_driver.get_playlist(from_playlist_id)
        target_playlist = target_driver.get_playlist(to_playlist_id)
        echo(
            style(
                f'Found source playlist "{source_playlist}" and '
                f'target playlist "{target_playlist}"',
                fg='blue',
            )
        )
        source_playlist_tracks = source_driver.get_playlist_tracks(
            playlist_id=from_playlist_id,
            limit=limit
        )
        target_playlist_tracks = target_driver.get_playlist_tracks(
            playlist_id=to_playlist_id,
            limit=0,
        )
    except PlaylistNotFoundException:
        raise UsageError('One or more playlist IDs are invalid.')
    except (OptionalDependencyException, ServiceDriverException) as e:
        raise UsageError(str(e)) from e

    synchronizer = PlaylistSynchronizer(
        source_driver=source_driver,
        target_driver=target_driver,
        match_policy=match_policy,
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

    order_needs_sync = False
    if not skipping_removals_due_to_limit:
        order_needs_sync = (
            len(source_playlist_tracks) != len(target_playlist_tracks)
            or any(
                not synchronizer.find_matching_track(source_track, [target_track])
                for source_track, target_track in zip(
                    source_playlist_tracks,
                    target_playlist_tracks,
                )
            )
        )

    if skipping_removals_due_to_limit and not tracks_to_add:
        echo(style('No tracks to add within the requested limit', fg='green'))
        return

    if not skipping_removals_due_to_limit and not order_needs_sync:
        echo(style('No tracks to sync, target playlist is up-to-date', fg='green'))
        return
    
    if order_needs_sync:
        echo(style('Target contents or order differ from the source', fg='blue'))

    if show_diff and len(tracks_to_add) > 0:
        echo(style('Tracks to add:', fg='yellow'))
        list_tracks(tracks_to_add, color='yellow')

    if show_diff and len(tracks_to_remove) > 0:
        echo(style('Tracks to remove:', fg='magenta'))
        list_tracks(tracks_to_remove, color='magenta')
    
    echo(style('Resolving the complete target track order...', fg='blue'))
    tracks_to_resolve = (
        tracks_to_add
        if skipping_removals_due_to_limit
        else source_playlist_tracks
    )
    existing_candidates = (
        []
        if skipping_removals_due_to_limit
        else target_playlist_tracks
    )
    try:
        desired_target_order, unmatched_tracks = synchronizer.resolve_target_order(
            tracks_to_resolve,
            existing_candidates,
        )
    except (OptionalDependencyException, ServiceDriverException) as e:
        echo(style(f"Failed to resolve target tracks: {e}", fg='red'))
        raise Abort() from e

    echo(
        style(
            f"Resolved {len(desired_target_order)} tracks in total",
            fg='blue' if desired_target_order else 'red',
        )
    )

    if len(unmatched_tracks) > 0:
        echo(
            style(
                f"Warning: {len(unmatched_tracks)} track(s) could not be matched. "
                "The target playlist was not modified.",
                fg='yellow',
            )
        )
        echo(style(COMMON_MATCH_ISSUE_REASON, fg='yellow'))

        if show_misses:
            list_tracks(unmatched_tracks, color='yellow')
        else:
            echo(style('Re-run this command with the --misses flag to automatically list the missing tracks.', fg='yellow'))
        raise Abort()

    if is_preview:
        echo(style("Preview complete; target playlist was not modified", fg='green'))
        return

    try:
        if skipping_removals_due_to_limit:
            target_driver.add_tracks_to_playlist(
                playlist_id=to_playlist_id,
                track_ids=[
                    track.service_id
                    for track in desired_target_order
                    if track.service_id is not None
                ],
            )
        else:
            synchronizer.apply_target_order(
                to_playlist_id,
                target_playlist_tracks,
                desired_target_order,
            )
    except UnsupportedFeatureException as e:
        echo(
            style(
                "Target service does not support a required playlist update "
                "operation; the sync could not be completed.",
                fg='red',
            )
        )
        raise Abort() from e
    except Exception as e:
        echo(style(f"Failed to update target playlist: {e}", fg='red'))
        raise Abort() from e

    if skipping_removals_due_to_limit:
        echo(style("Target playlist updated with the requested tracks", fg='green'))
    else:
        echo(style("Target playlist synchronized in source order", fg='green'))

    echo(style("Sync complete!", fg='green'))
