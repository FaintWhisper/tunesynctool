from typing import List, Optional

from tunesynctool.drivers import ServiceDriver
from tunesynctool.models import Track
from tunesynctool.features.track_matcher import TrackMatcher
from tunesynctool.utilities import clean_str, extract_core_title, calculate_str_similarity
from tunesynctool.exceptions import UnsupportedFeatureException

class PlaylistSynchronizer:
    """
    Attempts to synchronize a playlist between two services.
    """

    def __init__(self, source_driver: ServiceDriver, target_driver: ServiceDriver):
        """
        Initializes a new instance of PlaylistSynchronizer.

        :param source_driver: The driver for the source service.
        :param target_driver: The driver for the target service.
        """

        self.__source = source_driver
        self.__target = target_driver
        self.__target_matcher = TrackMatcher(target_driver)
    
    def find_missing_tracks(self, source_playlist_tracks: List[Track], target_playlist_tracks: List[Track], debug: bool = False) -> List[Track]:
        """
        Returns a list of tracks that are present in the source playlist but not in the target playlist.
        
        Compares tracks by their core titles and artists to avoid treating different versions
        (e.g., "Original Mix" vs "Instrumental Mix") as different tracks.
        
        Note: If the source playlist contains duplicates of the same track, only the first
        occurrence needs to be in the target. Additional duplicates are ignored.

        :param source_playlist_tracks: The tracks in the source playlist.
        :param target_playlist_tracks: The tracks in the target playlist.
        :param debug: If True, print debug information about comparisons.
        :return: A list of tracks that are present in the source playlist but not in the target playlist.
        """

        tracks_that_are_not_in_target_but_are_in_source = []
        # Don't use processed_target_tracks - allow same target track to match multiple source duplicates

        for source_track in source_playlist_tracks:
            match_found = False

            # Get core title and artist for source track
            source_core_title = clean_str(extract_core_title(source_track.title))
            source_artist = clean_str(source_track.primary_artist)
            
            if debug:
                print(f"\n[DEBUG] Checking source: {source_track.primary_artist} - {source_track.title}")
                print(f"        Core: '{source_core_title}' | Artist: '{source_artist}'")

            for target_track in target_playlist_tracks:
                # Removed the processed_target_tracks check to allow source duplicates
                # to match the same target track

                # First try exact matching (faster)
                if source_track.matches(target_track):
                    match_found = True
                    break
                
                # Then try core title matching (for different versions of same track)
                target_core_title = clean_str(extract_core_title(target_track.title))
                target_artist = clean_str(target_track.primary_artist)
                
                if debug:
                    print(f"        vs: {target_track.primary_artist} - {target_track.title}")
                    print(f"            Core: '{target_core_title}' | Artist: '{target_artist}'")
                
                # If core titles and artists are very similar, consider it the same track
                title_similarity = calculate_str_similarity(source_core_title, target_core_title)
                artist_similarity = calculate_str_similarity(source_artist, target_artist)
                
                if debug:
                    print(f"            Title sim: {title_similarity:.2f}, Artist sim: {artist_similarity:.2f}")
                
                # Check for artist word overlap if similarity is low
                if artist_similarity < 0.5:
                    source_artist_words = set(source_artist.split())
                    target_artist_words = set(target_artist.split())
                    if source_artist_words & target_artist_words:
                        artist_similarity = 0.7
                        if debug:
                            print(f"            Artist boosted to 0.70 (word overlap: {source_artist_words & target_artist_words})")
                
                # If both core title and artist match well, it's the same track (different version)
                if title_similarity >= 0.85 and artist_similarity >= 0.5:
                    match_found = True
                    if debug:
                        print(f"            ✓ MATCH FOUND")
                    break

            if not match_found:
                tracks_that_are_not_in_target_but_are_in_source.append(source_track)
                if debug:
                    print(f"        ✗ NO MATCH - marked as missing")

        return tracks_that_are_not_in_target_but_are_in_source
    
    def find_tracks_to_remove(self, source_playlist_tracks: List[Track], target_playlist_tracks: List[Track]) -> List[Track]:
        """
        Returns tracks that exist on the target playlist but not on the source playlist.

        This reuses the same comparison logic as find_missing_tracks by swapping the reference lists.
        """

        return self.find_missing_tracks(
            source_playlist_tracks=target_playlist_tracks,
            target_playlist_tracks=source_playlist_tracks
        )
    
    def sync(self, source_playlist_id: str, target_playlist_id: str) -> None:
        """
        Synchronizes the source playlist with the target playlist.
        
        This completely rebuilds the target playlist to match the source playlist's order.
        Tracks are matched intelligently to handle different versions (e.g., "Original Mix" vs "Instrumental Mix").

        :param source_playlist_id: The ID of the source playlist.
        :param target_playlist_id: The ID of the target playlist.
        :return: None
        """

        source_playlist_tracks = self.__source.get_playlist_tracks(
            playlist_id=source_playlist_id
        )
        target_playlist_tracks = self.__target.get_playlist_tracks(
            playlist_id=target_playlist_id
        )

        # Build the desired target playlist by matching each source track
        desired_target_order = []
        for source_track in source_playlist_tracks:
            # First, try to find the track in the existing target playlist
            matched_in_target = None
            for target_track in target_playlist_tracks:
                # Get core title and artist for comparison
                source_core_title = clean_str(extract_core_title(source_track.title))
                source_artist = clean_str(source_track.primary_artist)
                target_core_title = clean_str(extract_core_title(target_track.title))
                target_artist = clean_str(target_track.primary_artist)
                
                # Check if they match (same logic as find_missing_tracks)
                if source_track.matches(target_track):
                    matched_in_target = target_track
                    break
                
                title_similarity = calculate_str_similarity(source_core_title, target_core_title)
                artist_similarity = calculate_str_similarity(source_artist, target_artist)
                
                if artist_similarity < 0.5:
                    source_artist_words = set(source_artist.split())
                    target_artist_words = set(target_artist.split())
                    if source_artist_words & target_artist_words:
                        artist_similarity = 0.7
                
                if title_similarity >= 0.85 and artist_similarity >= 0.5:
                    matched_in_target = target_track
                    break
            
            # If found in existing target, use it; otherwise search the target service
            if matched_in_target:
                desired_target_order.append(matched_in_target)
            else:
                # Try to find the track on the target service
                searched_track = self.__target_matcher.find_match(track=source_track)
                if searched_track:
                    desired_target_order.append(searched_track)
                # If not found anywhere, skip this source track
        
        # Clear the target playlist and rebuild it in source order
        if target_playlist_tracks:
            try:
                self.__target.remove_tracks_from_playlist(
                    playlist_id=target_playlist_id,
                    track_ids=[track.service_id for track in target_playlist_tracks]
                )
            except UnsupportedFeatureException:
                pass
        
        # Add all tracks in the desired order
        if desired_target_order:
            self.__target.add_tracks_to_playlist(
                playlist_id=target_playlist_id,
                track_ids=[track.service_id for track in desired_target_order]
            )