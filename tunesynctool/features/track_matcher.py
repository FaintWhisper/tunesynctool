from typing import List, Optional

from tunesynctool.drivers import ServiceDriver
from tunesynctool.exceptions import TrackNotFoundException
from tunesynctool.models import Track
from tunesynctool.integrations import Musicbrainz
from tunesynctool.utilities import clean_str, extract_core_title

class TrackMatcher:
    """
    Attempts to find a matching track between the source and target services.
    """

    def __init__(self, target_driver: ServiceDriver) -> None:
        self._target = target_driver

    def find_match(self, track: Track) -> Optional[Track]:
        """
        Tries to match the track to one available on the target service itself.

        This is a best-effort operation and may not be perfect.
        There is no guarantee that the tracks will be matched correctly or that any will be matched at all.
        """

        # Strategy 0: If the track is suspected to originate from the same service, try to fetch it directly
        matched_track = self.__search_on_origin_service(track)
        if track.matches(matched_track):
            return matched_track
        
        # Strategy 1: If the track has an ISRC, try to search for it directly
        matched_track = self.__search_by_isrc_only(track)
        if track.matches(matched_track):
            return matched_track
        
        # Strategy 2: Using plain old text search
        matched_track = self.__search_with_text(track)
        if track.matches(matched_track):
            return matched_track

        # Stategy 3: Using the ISRC + MusicBrainz ID
        matched_track = self.__search_with_musicbrainz_id(track)
        if track.matches(matched_track):
            return matched_track

        # Strategy 4: Fallback with very lenient matching (ignores parenthetical content and lower threshold)
        matched_track = self.__search_with_lenient_matching(track)
        if matched_track:
            return matched_track

        # At this point we haven't found any matches unfortunately
        return None
    
    def __get_musicbrainz_id(self, track: Track) -> Optional[str]:
        """
        Fetches the MusicBrainz ID for a track.
        """

        if track.musicbrainz_id:
            return track.musicbrainz_id

        # musicbrainz_id = Musicbrainz.id_from_isrc(track.isrc)
        # if musicbrainz_id:
        #     return musicbrainz_id
        
        return Musicbrainz.id_from_track(track)
    
    def __search_with_musicbrainz_id(self, track: Track) -> Optional[Track]:
        """
        Searches for tracks using a MusicBrainz ID.
        Requires ISRC or Musicbrainz ID metadata to be available to work.
        """

        if not track.musicbrainz_id:
            track.musicbrainz_id = self.__get_musicbrainz_id(track)
        
        if not track.musicbrainz_id:
            return None
        
        if self._target.supports_musicbrainz_id_querying:
            results = self._target.search_tracks(
                query=track.musicbrainz_id,
                limit=1
            )

            if len(results) > 0:
                return results[0]
        
        return None
    
    def __search_with_text(self, track: Track) -> Optional[Track]:
        """
        Searches for tracks using plain text with multiple query variations.
        """

        # Get base strings
        title_clean = clean_str(track.title)
        artist_clean = clean_str(track.primary_artist)
        title_core = clean_str(extract_core_title(track.title))
        
        # Create multiple query variations to maximize chances of finding a match
        queries = []
        
        # Strategy 1: Full artist + full title
        if artist_clean and title_clean:
            queries.append(f'{artist_clean} {title_clean}')
        
        # Strategy 2: Artist + core title (without remix/feat info)
        if artist_clean and title_core and title_core != title_clean:
            queries.append(f'{artist_clean} {title_core}')
        
        # Strategy 3: Core title only (works well when artist metadata differs)
        if title_core:
            queries.append(title_core)
        
        # Strategy 4: Full title only
        if title_clean and title_clean != title_core:
            queries.append(title_clean)
        
        # Strategy 5: Artist only (last resort, will get many results)
        if artist_clean:
            queries.append(artist_clean)

        results: List[Track] = []
        seen_ids = set()
        
        # Search with each query, collecting unique results
        for query in queries:
            if not query:
                continue
            
            # Use different limits based on query specificity
            # More specific queries (artist + title) can have smaller limits
            # Less specific queries (title only, artist only) need larger limits
            if artist_clean and artist_clean in query and title_core and title_core in query:
                limit = 30  # Artist + title queries
            elif title_core and title_core in query and artist_clean not in query:
                limit = 50  # Title-only queries need more results
            else:
                limit = 40  # Everything else
                
            search_results = self._target.search_tracks(
                query=query,
                limit=limit
            )
            
            # Add only unique tracks
            for result in search_results:
                result_key = (result.service_id, result.service_name)
                if result_key not in seen_ids:
                    seen_ids.add(result_key)
                    results.append(result)

        # Try to find a match in all collected results
        for result in results:
            if track.matches(result):
                return result
            
        return None
    
    def __search_on_origin_service(self, track: Track) -> Optional[Track]:
        """
        If it is suspected that the track originates from the same service, it tries to fetch it directly.
        """

        if (track.service_name and self._target.service_name) and (track.service_name == self._target.service_name):
            maybe_match = self._target.get_track(track.service_id)
            
            if maybe_match and track.matches(maybe_match):
                return maybe_match
            
        return None
    
    def __search_by_isrc_only(self, track: Track) -> Optional[Track]:
        """
        If supported by the target service, this tries to search for a track using its ISRC.

        In theory, this should be the most reliable way to match tracks.
        """

        if not track.isrc or not self._target.supports_direct_isrc_querying:
            return None
        
        try:
            likely_match = self._target.get_track_by_isrc(
                isrc=track.isrc
            )

            if likely_match and track.matches(likely_match):
                return likely_match
        except TrackNotFoundException as e:
            pass

        return None
    
    def __search_with_lenient_matching(self, track: Track) -> Optional[Track]:
        """
        Fallback search with very lenient matching criteria.
        Ignores parenthetical content and uses lower similarity thresholds.
        """

        # Extract core title (without parenthetical content)
        core_title = clean_str(extract_core_title(track.title))
        artist = clean_str(track.primary_artist)
        
        if not core_title or not artist:
            return None
        
        # Search with just artist + core title
        queries = [
            f'{artist} {core_title}',
            core_title,
            artist
        ]
        
        results: List[Track] = []
        seen_ids = set()
        
        for query in queries:
            if not query:
                continue
                
            search_results = self._target.search_tracks(
                query=query,
                limit=50  # Cast a wide net
            )
            
            for result in search_results:
                result_key = (result.service_id, result.service_name)
                if result_key not in seen_ids:
                    seen_ids.add(result_key)
                    results.append(result)
        
        # Try matching with much lower threshold (0.60 instead of 0.75)
        for result in results:
            if track.matches(result, threshold=0.60):
                return result
        
        return None