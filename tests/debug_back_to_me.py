#!/usr/bin/env python
"""Debug why Back To Me is treated as missing"""
import sys
sys.path.insert(0, '.')

from tunesynctool.utilities import clean_str, extract_core_title, calculate_str_similarity

# Simulate the exact comparison
source_title = "Back To Me"
source_artist = "KSHMR"

target_title = "Back To Me (feat. Micky Blue)"
target_artist = "KSHMR • Crossnaders • Micky Blue"

# Extract core titles
source_core = clean_str(extract_core_title(source_title))
target_core = clean_str(extract_core_title(target_title))

# Calculate similarity
title_similarity = calculate_str_similarity(source_core, target_core)

# Artist comparison
source_artist_clean = clean_str(source_artist)
target_artist_clean = clean_str(target_artist)
artist_similarity = calculate_str_similarity(source_artist_clean, target_artist_clean)

print("=" * 70)
print("SOURCE TRACK:")
print(f"  Title: {source_title}")
print(f"  Core:  '{source_core}'")
print(f"  Artist: {source_artist}")
print(f"  Clean: '{source_artist_clean}'")
print()
print("TARGET TRACK:")
print(f"  Title: {target_title}")
print(f"  Core:  '{target_core}'")
print(f"  Artist: {target_artist}")
print(f"  Clean: '{target_artist_clean}'")
print()
print("SIMILARITY:")
print(f"  Title similarity: {title_similarity:.2f} (threshold: 0.85)")
print(f"  Artist similarity: {artist_similarity:.2f} (threshold: 0.50)")
print()

# Check word overlap
source_words = set(source_artist_clean.split())
target_words = set(target_artist_clean.split())
overlap = source_words & target_words

print("ARTIST WORD ANALYSIS:")
print(f"  Source words: {source_words}")
print(f"  Target words: {target_words}")
print(f"  Overlap: {overlap}")

if artist_similarity < 0.5 and overlap:
    artist_similarity = 0.7
    print(f"  Adjusted artist similarity: {artist_similarity:.2f}")

print()
print("MATCH DECISION:")
would_match = title_similarity >= 0.85 and artist_similarity >= 0.5
print(f"  Would match: {would_match}")
print(f"  Should match: True")
print()

if would_match:
    print("✓ CORRECT - Track would be detected as already present")
else:
    print("✗ PROBLEM - Track would be marked as missing!")
    if title_similarity < 0.85:
        print(f"  → Title similarity too low ({title_similarity:.2f} < 0.85)")
    if artist_similarity < 0.5:
        print(f"  → Artist similarity too low ({artist_similarity:.2f} < 0.50)")
