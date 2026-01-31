class GPSTracker:
    def __init__(self):
        self.pos = (0,0)

    def update(self, lat, lon):
        self.pos = (lat, lon)
        return True
