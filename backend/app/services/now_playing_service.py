class NowPlayingService:
    @staticmethod
    async def get_now_playing(station_id: int, stream_url: str) -> dict:
        """Stub for ICY metadata extraction from live audio stream."""
        return {
            "station_id": station_id,
            "title": None,
            "artist": None,
            "raw": None,
        }
