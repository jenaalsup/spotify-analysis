import os
import time
import pandas as pd
from datetime import datetime, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
load_dotenv() 

SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.environ.get('SPOTIPY_REDIRECT_URI')
SCOPE = 'user-read-recently-played'

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope=SCOPE,
    cache_path='.spotifycache'
))

def get_daily_song_counts(days=30):
    """
    Get a count of songs played per day over the specified time period
    Note: Due to Spotify API limitations, this may not get full history
    """
    daily_counts = {}
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    before = None
    track_limit = 50  
    
    print(f"Collecting song count data for the past {days} days...")
    
    pagination_count = 0
    max_pages = 10  
    
    while pagination_count < max_pages:
        try:
            if before:
                results = sp.current_user_recently_played(limit=track_limit, before=before)
            else:
                results = sp.current_user_recently_played(limit=track_limit)
            
            if not results or not results['items']:
                print("No more tracks available.")
                break
            
            found_in_range = False
            
            for item in results['items']:
                played_at = item['played_at']
                
                played_at_dt = datetime.strptime(played_at, '%Y-%m-%dT%H:%M:%S.%fZ')
                
                if played_at_dt < cutoff_date:
                    continue
                    
                found_in_range = True
                date_played = played_at_dt.strftime('%Y-%m-%d')
                
                if date_played in daily_counts:
                    daily_counts[date_played] += 1
                else:
                    daily_counts[date_played] = 1
            
            if results['items']:
                earliest_timestamp = datetime.strptime(
                    results['items'][-1]['played_at'], 
                    '%Y-%m-%dT%H:%M:%S.%fZ'
                ).timestamp() * 1000
                
                before = int(earliest_timestamp) - 1
                
                pagination_count += 1
                print(f"Page {pagination_count}: Collected data up to {datetime.fromtimestamp(before/1000).strftime('%Y-%m-%d')}...")
                
                if not found_in_range:
                    print("No more tracks in the specified date range.")
                    break
            else:
                break
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            time.sleep(5)  
            pagination_count += 1  
    
    if daily_counts:
        date_range = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            date_range.append(date)
        
        df = pd.DataFrame({
            'date': date_range,
            'song_count': [daily_counts.get(date, 0) for date in date_range]
        })
        
        df = df.sort_values(by='date')
        
        return df
    else:
        return pd.DataFrame(columns=['date', 'song_count'])

def main():
    print("Fetching your Spotify song counts for the past 30 days...")
    daily_counts = get_daily_song_counts(days=30)
    
    if not daily_counts.empty:
        # Save daily counts
        daily_counts.to_csv('spotify_daily_song_counts.csv', index=False)
        print(f"Saved daily song counts to spotify_daily_song_counts.csv")
        
        # Display summary
        print("\nSummary of your listening history:")
        print(f"Total days with data: {(daily_counts['song_count'] > 0).sum()} out of {len(daily_counts)}")
        print(f"Total songs listened to: {daily_counts['song_count'].sum()}")
        print(f"Average songs per day: {daily_counts['song_count'].mean():.2f}")
        if daily_counts['song_count'].max() > 0:
            max_day = daily_counts.loc[daily_counts['song_count'].idxmax()]
            print(f"Maximum songs in a day: {max_day['song_count']} (on {max_day['date']})")
    else:
        print("No listening history retrieved. Check your Spotify API credentials and permissions.")

if __name__ == "__main__":
    main()