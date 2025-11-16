import re

s = "Resurrection - Axwell's Recut Radio Version"
pattern = r'\s*-\s*(?:(?:Original|Instrumental|Extended|Radio|Club|Dub|Vocal|Acapella|Official|[\w\s]+?\s+)?(?:Radio\s+)?(?:Edit|Remix|Mix|Version|Remaster|Live|Acoustic|Instrumental))'
result = re.split(pattern, s, maxsplit=1, flags=re.IGNORECASE)
print('Input:', s)
print('Result:', result)
print('Match found:', len(result) > 1)

# Try simpler pattern
pattern2 = r'\s*-\s*.+?(Edit|Remix|Mix|Version|Remaster|Live|Acoustic|Instrumental)'
result2 = re.split(pattern2, s, maxsplit=1, flags=re.IGNORECASE)
print('\nSimpler pattern result:', result2)
