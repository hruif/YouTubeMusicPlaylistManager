from thefuzz import process
from datetime import datetime
from song import Song

# --------------------------- NEED TESTING ---------------------------------------------------------------

# Playlist
sorting = "date"
songs = []

# Add song to playlist
def addSong(song: Song, time_added: float):
    songs.add((song, time_added))
    if (sorting == "date"):
        sortByDate()
    elif (sorting == "name"):
        sortByName()

# Remove song from playlist
def removeSong(song: Song):
    songs = [pair for pair in songs if pair[0] != song]

# Search within playlist
def search(query: str):
    results = process.extract(query, songs, limit=10)
    return results

# Check if song is within the playlist
def isInPlaylist(song: Song):
    return (song in songs)

# Sort playlist by date added
def sortByDate():
    songs = sorted(songs, key=lambda pair: pair[1])
    sorting = "date"

# Sort playlist by name
def sortByName():
    songs = sorted(songs, key=lambda pair: pair[0].name)
    sorting = "name"