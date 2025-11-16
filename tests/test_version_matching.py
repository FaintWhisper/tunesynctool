#!/usr/bin/env python
"""Test version matching behavior"""
import sys
sys.path.insert(0, '.')

from tunesynctool.utilities import clean_str, extract_core_title, calculate_str_similarity

# Test the normalization
test_cases = [
    ("White Lies - Original Mix", "White Lies - Instrumental Mix", True),
    ("Back To Me", "Back To Me (feat. Micky Blue)", True),
    ("Resurrection - Axwell's Recut Radio Version", "Resurrection (Axwell's Recut club version)", True),
    ("White Lies - Original Mix", "Stars (original mix)", False),
]

for title1, title2, should_match in test_cases:
    core1 = clean_str(extract_core_title(title1))
    core2 = clean_str(extract_core_title(title2))
    similarity = calculate_str_similarity(core1, core2)
    
    print(f"\n{'=' * 70}")
    print(f"Title 1: {title1}")
    print(f"  Core: '{core1}'")
    print(f"Title 2: {title2}")
    print(f"  Core: '{core2}'")
    print(f"Similarity: {similarity:.2f}")
    print(f"Should match: {should_match}, Would match (>= 0.85): {similarity >= 0.85}")
    print(f"✓ PASS" if (similarity >= 0.85) == should_match else "✗ FAIL")
