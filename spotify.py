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
SCOPE = 'user-read-recently-played user-top-read'

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


def get_top_tracks_estimate(time_range='short_term', limit=50):
    """
    Get top tracks and estimate daily play counts from top track data
    time_range options: short_term (~4 weeks), medium_term (~6 months), long_term (all time)
    """
    print(f"Fetching your top tracks for {time_range}...")
    
    # Get top tracks for the specified time range
    results = sp.current_user_top_tracks(limit=limit, time_range=time_range)
    
    if not results or 'items' not in results or not results['items']:
        print("No top tracks found for this time period.")
        return pd.DataFrame(columns=['date', 'song_count'])
    
    total_tracks = len(results['items'])
    print(f"Found {total_tracks} top tracks.")
    
    # Get a rough estimate of days in the period
    days_in_period = 28 if time_range == 'short_term' else (180 if time_range == 'medium_term' else 365)
    
    # Create an approximate distribution of plays
    daily_counts = {}
    today = datetime.now()
    
    # Create a weight curve - higher ranked songs were likely played more recently and more often
    for i, item in enumerate(results['items']):
        weight = (total_tracks - i) / total_tracks  # Normalized weight based on rank
        
        # Distribute plays across the time range with higher concentration in recent days
        for day in range(min(days_in_period, 30)):  # Only consider last 30 days for short_term
            # More weight to recent days, less to older days
            day_weight = (30 - day) / 30
            play_estimate = round(weight * day_weight * 2)  # Scaling factor
            
            if play_estimate > 0:
                date = (today - timedelta(days=day)).strftime('%Y-%m-%d')
                if date in daily_counts:
                    daily_counts[date] += play_estimate
                else:
                    daily_counts[date] = play_estimate
    
    # Convert to DataFrame
    date_range = []
    for i in range(30):  # Always return last 30 days
        date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        date_range.append(date)
    
    df = pd.DataFrame({
        'date': date_range,
        'song_count': [daily_counts.get(date, 0) for date in date_range]
    })
    
    df = df.sort_values(by='date')
    
    return df

def main():
    print("Fetching Spotify song counts for the past 30 days...")
    
    recent_counts = get_daily_song_counts(days=30)
    
    top_track_counts = get_top_tracks_estimate(time_range='short_term')
    
    if not recent_counts.empty and not top_track_counts.empty:
        combined_df = recent_counts.merge(top_track_counts, on='date', how='outer', suffixes=('_recent', '_top'))
        
        combined_df['song_count'] = combined_df.apply(
            lambda row: row['song_count_recent'] if row['song_count_recent'] > 0 else row['song_count_top'], 
            axis=1
        )
        
        daily_counts = combined_df[['date', 'song_count']]
        daily_counts = daily_counts.sort_values(by='date')
    else:
        daily_counts = recent_counts if not recent_counts.empty else top_track_counts
    
    if not daily_counts.empty:
        daily_counts.to_csv('spotify_daily_song_counts.csv', index=False)
        print(f"Saved daily song counts to spotify_daily_song_counts.csv")
        
        print("\nSummary of your listening history:")
        print(f"Total days with data: {(daily_counts['song_count'] > 0).sum()} out of {len(daily_counts)}")
        print(f"Total songs (estimated): {daily_counts['song_count'].sum()}")
        print(f"Average songs per day: {daily_counts['song_count'].mean():.2f}")
        if daily_counts['song_count'].max() > 0:
            max_day = daily_counts.loc[daily_counts['song_count'].idxmax()]
            print(f"Maximum songs in a day: {max_day['song_count']} (on {max_day['date']})")
        print("\nNote: Due to Spotify API limitations, some counts are estimated based on your top tracks.")
    else:
        print("No listening history retrieved. Check your Spotify API credentials and permissions.")

if __name__ == "__main__":
    main()