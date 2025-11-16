#!/usr/bin/env python
"""Test with actual Spotify and Navidrome data"""
import sys
import os
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

from tunesynctool import Configuration, SpotifyDriver, SubsonicDriver, PlaylistSynchronizer

config = Configuration.from_env()
spotify = SpotifyDriver(config)
navidrome = SubsonicDriver(config)

# Get playlists from environment
spotify_playlist_id = os.getenv('SPOTIFY_PLAYLIST_ID')
navidrome_playlist_id = os.getenv('NAVIDROME_PLAYLIST_ID')

print("Fetching playlists...")
spotify_tracks = spotify.get_playlist_tracks(spotify_playlist_id)
navidrome_tracks = navidrome.get_playlist_tracks(navidrome_playlist_id)

print(f"\nSpotify has {len(spotify_tracks)} tracks")
print(f"Navidrome has {len(navidrome_tracks)} tracks")

# Find "Back To Me" in both
print("\n" + "=" * 70)
print("SEARCHING FOR 'BACK TO ME' IN BOTH PLAYLISTS")
print("=" * 70)

spotify_back_to_me = [t for t in spotify_tracks if 'back to me' in t.title.lower()]
navidrome_back_to_me = [t for t in navidrome_tracks if 'back to me' in t.title.lower()]

print(f"\nSpotify 'Back To Me' tracks: {len(spotify_back_to_me)}")
for t in spotify_back_to_me:
    print(f"  - '{t.title}' by '{t.primary_artist}'")

print(f"\nNavidrome 'Back To Me' tracks: {len(navidrome_back_to_me)}")
for t in navidrome_back_to_me:
    print(f"  - '{t.title}' by '{t.primary_artist}'")

# Run find_missing_tracks with debug
print("\n" + "=" * 70)
print("RUNNING find_missing_tracks WITH DEBUG")
print("=" * 70)

synchronizer = PlaylistSynchronizer(spotify, navidrome)
missing = synchronizer.find_missing_tracks(
    source_playlist_tracks=spotify_tracks,
    target_playlist_tracks=navidrome_tracks,
    debug=True
)

print(f"\n\nMissing tracks: {len(missing)}")
for t in missing:
    print(f"  - {t}")
