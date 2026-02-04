import json
import subprocess
import os
import sys

# Increase recursion depth for deep expression trees
sys.setrecursionlimit(200000)

def build_tree(times, values, start, end):
    if start == end:
        return f"{values[start]:.2f}"
    mid = (start + end) // 2
    return f"if(lt(t,{times[mid]:.4f}),{build_tree(times, values, start, mid)},{build_tree(times, values, mid + 1, end)})"

def generate_render_script(duration_limit=None):
    print(f"Loading cursor.json...")
    with open('segments/segment-0/cursor.json', 'r') as f:
        data = json.load(f)

    moves = data.get('moves', [])
    if duration_limit:
        moves = [m for m in moves if m['time_ms']/1000.0 <= duration_limit]
    
    if not moves:
        print("No moves found!")
        return

    times = [m['time_ms'] / 1000.0 for m in moves]
    xs = [m['x'] * 1920 for m in moves]
    ys = [m['y'] * 1080 for m in moves]
    ids = [int(m['cursor_id']) for m in moves]

    print(f"Building expression trees ({len(moves)} points)...")
    x_expr = build_tree(times, xs, 0, len(moves) - 1)
    y_expr = build_tree(times, ys, 0, len(moves) - 1)
    id_expr = build_tree(times, ids, 0, len(moves) - 1)

    print(f"Building FFmpeg command...")
    
    inputs = [
        '-i', 'segments/segment-0/display.mp4',
        '-i', 'segments/segment-0/camera.mp4',
        '-i', 'segments/segment-0/audio-input.ogg'
    ]
    for i in range(11):
        inputs.extend(['-i', f'cursors/cursor_{i}.png'])

    filters = []
    # Camera overlay
    filters.append("[1:v] scale=360:202, format=rgba, geq=lum='p(X,Y)':a='if(lte(pow(max(0,abs(X-180)-160),2)+pow(max(0,abs(Y-101)-81),2),400),255,0)' [cam];")
    filters.append("[0:v][cam] overlay=W-w-20:20 [bg];")
    
    # Pad and stack cursors
    for i in range(11):
        filters.append(f"[{i+3}:v] pad=32:32:(32-iw)/2:(32-ih)/2:color=black@0 [cp{i}];")
    
    cursor_pads = "".join([f"[cp{i}]" for i in range(11)])
    filters.append(f"{cursor_pads} vstack=inputs=11 [atlas];")
    filters.append(f"[atlas] crop=32:32:0:'({id_expr})*32' [cursor];")
    filters.append(f"[bg][cursor] overlay=x='{x_expr}':y='{y_expr}':eval=frame [outv];")
    
    with open('filter_script.txt', 'w') as f:
        f.write("\n".join(filters))

    cmd = [
        'ffmpeg', '-y',
        *inputs,
        '-/filter_complex', 'filter_script.txt',
        '-map', '[outv]',
        '-map', '2:a',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k'
    ]
    
    if duration_limit:
        cmd.extend(['-t', str(duration_limit)])
        output_name = 'output_test.mp4'
    else:
        output_name = 'output_full.mp4'
    
    cmd.append(output_name)
    
    print("Executing FFmpeg...")
    # For full render, we might want to see progress
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
    
    for line in process.stdout:
        if "frame=" in line:
            print(line.strip(), end='\r')
        elif "Error" in line:
            print(line.strip())
            
    process.wait()
    if process.returncode != 0:
        print(f"\nError during FFmpeg execution. Return code: {process.returncode}")
    else:
        print(f"\nSuccess! {output_name} created.")

if __name__ == "__main__":
    # To run full render, set to None
    generate_render_script(None)
