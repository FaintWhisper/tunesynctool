from typing import List, Optional

from tunesynctool.drivers import ServiceDriver
from tunesynctool.exceptions import ServiceDriverException, TrackNotFoundException
from tunesynctool.features.track_matcher import TrackMatcher
from tunesynctool.models import MatchPolicy, Track


class PlaylistSynchronizer:
    """
    Attempts to synchronize a playlist between two services.
    """

    def __init__(
        self,
        source_driver: ServiceDriver,
        target_driver: ServiceDriver,
        *,
        match_policy: MatchPolicy | str = MatchPolicy.STRICT,
    ):
        """
        Initializes a new instance of PlaylistSynchronizer.

        :param source_driver: The driver for the source service.
        :param target_driver: The driver for the target service.
        """

        self.__source = source_driver
        self.__target = target_driver
        self.__target_matcher = TrackMatcher(
            target_driver,
            policy=match_policy,
        )

    def find_matching_track(
        self,
        source_track: Track,
        candidate_tracks: List[Track],
    ) -> Optional[Track]:
        """Return the best compatible existing track, if one is unambiguous."""

        return self.__target_matcher.select_best_candidate(
            source_track,
            candidate_tracks,
        )

    def find_missing_tracks(
        self,
        source_playlist_tracks: List[Track],
        target_playlist_tracks: List[Track],
    ) -> List[Track]:
        """
        Return source tracks that are not present in the target playlist.

        Uses the configured recording policy and the same ranked evaluator as
        remote track search.

        Note: If the source playlist contains duplicates of the same track, only the first
        occurrence needs to be in the target. Additional duplicates are ignored.

        :param source_playlist_tracks: The tracks in the source playlist.
        :param target_playlist_tracks: The tracks in the target playlist.
        :return: A list of tracks that are present in the source playlist but not in the target playlist.
        """

        tracks_that_are_not_in_target_but_are_in_source = []
        # Don't use processed_target_tracks - allow same target track to match multiple source duplicates

        for source_track in source_playlist_tracks:
            matched_track = self.find_matching_track(
                source_track,
                target_playlist_tracks,
            )

            if not matched_track:
                tracks_that_are_not_in_target_but_are_in_source.append(source_track)

        return tracks_that_are_not_in_target_but_are_in_source

    def find_tracks_to_remove(
        self,
        source_playlist_tracks: List[Track],
        target_playlist_tracks: List[Track],
    ) -> List[Track]:
        """
        Returns tracks that exist on the target playlist but not on the source playlist.

        This reuses the same comparison logic as find_missing_tracks by swapping the reference lists.
        """

        return self.find_missing_tracks(
            source_playlist_tracks=target_playlist_tracks,
            target_playlist_tracks=source_playlist_tracks,
        )

    def resolve_target_order(
        self,
        source_playlist_tracks: List[Track],
        target_playlist_tracks: List[Track],
    ) -> tuple[List[Track], List[Track]]:
        """Resolve every source entry to a usable target-service track.

        The first returned list preserves source order. The second contains
        source tracks that could not be resolved. No playlist mutations are
        performed by this method.
        """

        desired_target_order: List[Track] = []
        unmatched_tracks: List[Track] = []

        for source_track in source_playlist_tracks:
            resolved_track = self.find_matching_track(
                source_track,
                target_playlist_tracks,
            )

            if resolved_track is None or resolved_track.service_id is None:
                resolved_track = self.__target_matcher.find_match(track=source_track)

            if resolved_track is None or resolved_track.service_id is None:
                unmatched_tracks.append(source_track)
            else:
                desired_target_order.append(resolved_track)

        return desired_target_order, unmatched_tracks

    def apply_target_order(
        self,
        target_playlist_id: str,
        current_target_tracks: List[Track],
        desired_target_order: List[Track],
    ) -> None:
        """Replace a target playlist after its complete order has been resolved."""

        current_track_ids: List[str] = []
        for track in current_target_tracks:
            if track.service_id is None:
                raise ServiceDriverException(
                    "A current target track has no service ID; "
                    "target playlist was not modified."
                )
            current_track_ids.append(track.service_id)

        desired_track_ids: List[str] = []
        for track in desired_target_order:
            if track.service_id is None:
                raise ServiceDriverException(
                    "A resolved target track has no service ID; "
                    "target playlist was not modified."
                )
            desired_track_ids.append(track.service_id)

        if current_track_ids == desired_track_ids:
            return

        if current_track_ids:
            self.__target.remove_tracks_from_playlist(
                playlist_id=target_playlist_id,
                track_ids=current_track_ids,
            )

        if desired_track_ids:
            try:
                self.__target.add_tracks_to_playlist(
                    playlist_id=target_playlist_id,
                    track_ids=desired_track_ids,
                )
            except Exception:
                rollback_errors = []

                try:
                    self.__target.remove_tracks_from_playlist(
                        playlist_id=target_playlist_id,
                        track_ids=desired_track_ids,
                    )
                except Exception as error:
                    rollback_errors.append(error)

                if current_track_ids:
                    try:
                        self.__target.add_tracks_to_playlist(
                            playlist_id=target_playlist_id,
                            track_ids=current_track_ids,
                        )
                    except Exception as error:
                        rollback_errors.append(error)

                if rollback_errors:
                    raise ServiceDriverException(
                        "Target playlist update failed and its original order "
                        "could not be fully restored."
                    ) from ExceptionGroup(
                        "Playlist rollback failures",
                        rollback_errors,
                    )
                raise

    def sync(self, source_playlist_id: str, target_playlist_id: str) -> None:
        """
        Synchronizes the source playlist with the target playlist.

        This completely rebuilds the target playlist to match the source playlist's order.
        Tracks are matched with the configured strict or relaxed recording
        policy.

        :param source_playlist_id: The ID of the source playlist.
        :param target_playlist_id: The ID of the target playlist.
        :return: None
        """

        source_playlist_tracks = self.__source.get_playlist_tracks(
            playlist_id=source_playlist_id,
            limit=0,
        )
        target_playlist_tracks = self.__target.get_playlist_tracks(
            playlist_id=target_playlist_id,
            limit=0,
        )

        desired_target_order, unmatched_tracks = self.resolve_target_order(
            source_playlist_tracks,
            target_playlist_tracks,
        )
        if unmatched_tracks:
            raise TrackNotFoundException(
                f"{len(unmatched_tracks)} source track(s) could not be matched; "
                "target playlist was not modified."
            )

        self.apply_target_order(
            target_playlist_id,
            target_playlist_tracks,
            desired_target_order,
        )
