import json
from datetime import datetime
from collections import defaultdict

daily_counts = defaultdict(int)

files = [
  'Streaming_History_Audio_2023-2024_7.json',
  'Streaming_History_Audio_2024-2025_8.json' 
]

for file in files:
    with open(file, 'r') as f:
        data = json.load(f)
        for song in data:
            timestamp = datetime.strptime(song['ts'], '%Y-%m-%dT%H:%M:%SZ')
            if timestamp.year == 2024:
                date_str = timestamp.strftime('%Y-%m-%d')
                if song['master_metadata_track_name'] is not None:
                    daily_counts[date_str] += 1

sorted_counts = dict(sorted(daily_counts.items()))

with open('daily_song_counts_2024.json', 'w') as f:
    json.dump(sorted_counts, f, indent=2)
