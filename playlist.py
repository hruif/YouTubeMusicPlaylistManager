from thefuzz import process
from song.py import Song

# Playlist
songs = []

# Add song to playlist
def addSong(song):
    songs.add(song)

# Remove song from playlist
def removeSong(song):
    songs.remove(song)

# Search within playlist
def search(query):
    results = process.extract(query, songs, limit=10)
    return results

# Check if song is within the playlist
def isInPlaylist(song):
    return (song in songs)

def sortByDate(song):
