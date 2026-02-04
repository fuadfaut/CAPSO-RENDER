import os
import json

def setup_dummy():
    folders = [
        'cursors',
        'segments/segment-0'
    ]
    for f in folders:
        os.makedirs(f, exist_ok=True)
    
    # Create a dummy cursor.json
    dummy_cursor = {
        "moves": [
            {"cursor_id": "0", "time_ms": 0, "x": 0.1, "y": 0.1},
            {"cursor_id": "0", "time_ms": 1000, "x": 0.9, "y": 0.9}
        ],
        "clicks": []
    }
    
    with open('segments/segment-0/cursor.json', 'w') as f:
        json.dump(dummy_cursor, f)
        
    print("Dummy structure created.")
    print("Note: You still need real camera.mp4, display.mp4, and audio-input.ogg to render.")

if __name__ == "__main__":
    setup_dummy()
