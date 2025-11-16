from dataclasses import dataclass, field
from typing import List, Optional, Self

from tunesynctool.utilities import clean_str, calculate_str_similarity, calculate_int_closeness, extract_core_title

@dataclass
class Track:
    """Represents a single track."""

    title: str = field(default=None)
    """Title of the track."""
    
    album_name: Optional[str] = field(default=None)
    """Name of the album containing the track."""

    primary_artist: Optional[str] = field(default=None)
    """Primary (album) artist for the track."""

    additional_artists: List[str] = field(default_factory=list)
    """Additional artist names for the track."""

    duration_seconds: Optional[int] = field(default=None)
    """Duration of the track in seconds."""

    track_number: Optional[int] = field(default=None)
    """Track number on the album."""

    release_year: Optional[int] = field(default=None)
    """Year the track was released."""

    isrc: Optional[str] = field(default=None)
    """International Standard Recording Code for the track."""

    musicbrainz_id: Optional[str] = field(default=None)
    """MusicBrainz ID for the track."""
    
    service_id: Optional[str] = field(default=None)
    """Source-service specific ID for the track."""

    service_name: str = field(default='unknown')
    """Source service for the track."""

    service_data: Optional[dict] = field(default_factory=dict)
    """Raw JSON response data from the source service."""

    def __str__(self) -> str:
        return f"{self.track_number}. - {self.primary_artist} - {self.title}"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other: Optional[Self]) -> bool:
        if not other:
            return False
        
        return self.service_id == other.service_id and self.service_name == other.service_name
    
    def __hash__(self):
        return hash((self.service_id, self.service_name))

    def matches(self, other: Optional[Self], threshold: float = 0.75) -> bool:
        """
        Compares two tracks for equality, regardless of their source service.
        For primitive matching, use the __eq__ method (== operator).

        This is not 100% accurate, but it's good enough in most cases.
        """

        if not other:
            return False
        
        if (self.isrc and other.isrc) and self.isrc == other.isrc:
            return True
        elif (self.musicbrainz_id and other.musicbrainz_id) and self.musicbrainz_id == other.musicbrainz_id:
            return True
        
        # Compare both full titles and core titles (without featured artists/version info)
        title_similarity = calculate_str_similarity(clean_str(self.title), clean_str(other.title))
        core_title_similarity = calculate_str_similarity(
            clean_str(extract_core_title(self.title)), 
            clean_str(extract_core_title(other.title))
        )
        # Use the better of the two similarities
        best_title_similarity = max(title_similarity, core_title_similarity)
        
        artist_similarity = calculate_str_similarity(clean_str(self.primary_artist), clean_str(other.primary_artist))

        # If title similarity is very low, it's definitely not a match
        if best_title_similarity < 0.65:
            return False
        
        # For artist similarity, be more lenient since:
        # 1. Featured artists may be included differently (in title vs as separate artist)
        # 2. Collaborations may list artists in different order
        # 3. Artist names may have different capitalization or separators
        # Allow matches with lower artist similarity if title similarity is high
        if artist_similarity < 0.5:
            # If title is very similar, check if one artist string contains parts of the other
            if best_title_similarity >= 0.85:
                # Check if any word from one artist appears in the other
                self_artist_words = set(clean_str(self.primary_artist).split())
                other_artist_words = set(clean_str(other.primary_artist).split())
                
                # If there's any overlap in artist names, consider it valid
                if self_artist_words & other_artist_words:
                    # Boost artist similarity more for word overlap to ensure match passes threshold
                    artist_similarity = 0.7
                else:
                    return False
            else:
                return False
        
        weights = {
            'title': 4.0,
            'artist': 2.5,  # Reduced from 3.0 to be more lenient
            'album': 1.25 if self.album_name and other.album_name else 0.75,
            'duration': 0.75,
            'track': 0.5 if self.track_number and other.track_number else 0,
            'year': 0.5 if self.track_number and other.track_number else 0,
        }

        variables = [
            best_title_similarity * weights['title'],
            artist_similarity * weights['artist'],
            calculate_str_similarity(clean_str(self.album_name), clean_str(other.album_name)) * weights['album'],
            calculate_int_closeness(self.duration_seconds, other.duration_seconds) * weights['duration'],
            calculate_int_closeness(self.track_number, other.track_number) * weights['track'],
            calculate_int_closeness(self.release_year, other.release_year) * weights['year'],
        ]

        similarity_ratio = round(sum(variables) / sum(weights.values()), 2)

        return similarity_ratio >= threshold