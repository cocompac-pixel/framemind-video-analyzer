import json

with open('videos_analyzed/analisis_completo_20260114_134104.json', 'r') as f:
    data = json.load(f)

for video_id, video_data in data.get('videos', {}).items():
    print(f'Video: {video_data.get("filename", video_id)}')
    for seg in video_data.get('segments', []):
        tier = seg.get('tier', '?')
        score = seg.get('score', 0)
        is_garbage = seg.get('is_garbage', False)
        is_key = seg.get('is_key_moment', False)
        is_best = seg.get('is_best_take', False)
        is_repeated = seg.get('is_repeated_take', False)
        
        flags = []
        if is_garbage: flags.append('GARBAGE')
        if is_key: flags.append('KEY')
        if is_best: flags.append('BEST')
        if is_repeated: flags.append('REPEATED')
        
        flags_str = ', '.join(flags) if flags else '-'
        print(f'  {seg.get("id","?")}: tier={tier}, score={score:.1f}, flags=[{flags_str}]')
