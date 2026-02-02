#!/usr/bin/env python3
"""
Generador de reportes HTML con explicabilidad completa
"""

from datetime import datetime


def generate_detailed_report(results, stats, config, output_path):
    """Genera reporte HTML con expedientes detallados por segmento"""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # CSS
    css = """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
            background: #FBFBFD; 
            color: #1D1D1F; 
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }
        .container { max-width: 1100px; margin: 0 auto; padding: 60px 40px; }
        
        header { margin-bottom: 48px; }
        h1 { font-size: 40px; font-weight: 600; letter-spacing: -0.5px; margin-bottom: 8px; }
        .subtitle { font-size: 17px; color: #86868B; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 16px;
            margin-bottom: 40px;
        }
        .stat-card {
            background: #FFFFFF;
            border: 1px solid #E5E5E7;
            border-radius: 12px;
            padding: 20px;
        }
        .stat-value { font-size: 28px; font-weight: 600; }
        .stat-value.gold { color: #AF8700; }
        .stat-value.silver { color: #6B7280; }
        .stat-value.green { color: #34C759; }
        .stat-label { font-size: 13px; color: #86868B; margin-top: 4px; }
        
        .progress-bar {
            height: 8px;
            background: #E5E5E7;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 40px;
        }
        .progress-bar-inner {
            display: flex;
            height: 100%;
        }
        .progress-gold { background: #D4A800; }
        .progress-silver { background: #9CA3AF; }
        .progress-bronze { background: #B45309; }
        .progress-discard { background: #D1D5DB; }
        
        .section-title {
            font-size: 13px;
            font-weight: 600;
            color: #86868B;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 16px;
            margin-top: 40px;
        }
        
        .video-card {
            background: #FFFFFF;
            border: 1px solid #E5E5E7;
            border-radius: 12px;
            margin-bottom: 16px;
            overflow: hidden;
        }
        .video-header {
            padding: 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .video-header:hover { background: #F9FAFB; }
        .video-name { font-size: 17px; font-weight: 500; }
        .video-meta { font-size: 14px; color: #86868B; }
        .video-usable {
            font-size: 15px;
            font-weight: 600;
            color: #34C759;
        }
        
        .video-details { 
            display: none; 
            border-top: 1px solid #E5E5E7;
        }
        .video-details.open { display: block; }
        
        .timeline {
            padding: 20px;
            background: #F9FAFB;
        }
        .timeline-bar {
            height: 40px;
            background: #E5E5E7;
            border-radius: 6px;
            display: flex;
            overflow: hidden;
            position: relative;
        }
        .timeline-segment {
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 500;
            color: white;
            cursor: pointer;
            transition: opacity 0.2s;
            min-width: 2px;
        }
        .timeline-segment:hover { opacity: 0.8; }
        .timeline-segment.gold { background: #D4A800; }
        .timeline-segment.silver { background: #9CA3AF; }
        .timeline-segment.bronze { background: #B45309; }
        .timeline-segment.discard { background: #6B7280; }
        
        .segments-list { padding: 20px; }
        
        .segment-card {
            border: 1px solid #E5E5E7;
            border-radius: 10px;
            margin-bottom: 12px;
            overflow: hidden;
        }
        .segment-header {
            padding: 16px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            cursor: pointer;
        }
        .segment-header:hover { background: #F9FAFB; }
        
        .segment-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .segment-badge.gold { background: #FEF3C7; color: #92400E; }
        .segment-badge.silver { background: #F3F4F6; color: #374151; }
        .segment-badge.bronze { background: #FFEDD5; color: #9A3412; }
        .segment-badge.discard { background: #FEE2E2; color: #991B1B; }
        
        .segment-type {
            font-size: 14px;
            color: #1D1D1F;
            margin-top: 6px;
        }
        .segment-time {
            font-size: 13px;
            color: #86868B;
        }
        .segment-score {
            font-size: 24px;
            font-weight: 600;
        }
        
        .segment-details {
            display: none;
            padding: 16px;
            background: #F9FAFB;
            border-top: 1px solid #E5E5E7;
        }
        .segment-details.open { display: block; }
        
        .criteria-list { margin-top: 12px; }
        .criterion {
            display: flex;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #E5E5E7;
        }
        .criterion:last-child { border-bottom: none; }
        .criterion-icon {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            margin-right: 12px;
        }
        .criterion-icon.pass { background: #D1FAE5; color: #065F46; }
        .criterion-icon.fail { background: #FEE2E2; color: #991B1B; }
        .criterion-name { font-weight: 500; flex: 1; }
        .criterion-value { color: #86868B; font-size: 14px; }
        
        .explanation-box {
            background: #FFFFFF;
            border: 1px solid #E5E5E7;
            border-radius: 8px;
            padding: 16px;
            margin-top: 12px;
        }
        .explanation-title {
            font-size: 13px;
            font-weight: 600;
            color: #86868B;
            margin-bottom: 8px;
        }
        
        .shot-type-tag {
            display: inline-block;
            padding: 2px 8px;
            background: #E5E5E7;
            border-radius: 4px;
            font-size: 12px;
            margin-left: 8px;
        }
        
        .blurry-tag {
            display: inline-block;
            padding: 2px 8px;
            background: #FEE2E2;
            color: #991B1B;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 8px;
        }
        
        .segment-card.blurry {
            border-color: #FCA5A5;
            background: #FEF2F2;
        }
        
        .filter-bar {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 8px 16px;
            border: 1px solid #E5E5E7;
            border-radius: 20px;
            background: #FFFFFF;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .filter-btn:hover { border-color: #86868B; }
        .filter-btn.active { background: #1D1D1F; color: #FFFFFF; border-color: #1D1D1F; }
        
        .search-box {
            padding: 12px 16px;
            border: 1px solid #E5E5E7;
            border-radius: 10px;
            font-size: 15px;
            width: 100%;
            max-width: 300px;
            margin-bottom: 20px;
        }
        .search-box:focus { outline: none; border-color: #86868B; }
        
        @media (max-width: 768px) {
            .container { padding: 30px 20px; }
            h1 { font-size: 28px; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    """
    
    # Generar HTML de videos
    videos_html = ""
    for video in results:
        if not video.get('success'):
            continue
        
        segments = video.get('segments', [])
        duration = video.get('duration', 0)
        tier_durations = video.get('tier_durations', {})
        
        gold_dur = tier_durations.get('gold', 0)
        silver_dur = tier_durations.get('silver', 0)
        usable_pct = ((gold_dur + silver_dur) / duration * 100) if duration > 0 else 0
        
        # Timeline HTML
        timeline_segments = ""
        for seg in segments:
            seg_pct = (seg['duration'] / duration * 100) if duration > 0 else 0
            tier = seg.get('tier', 'discard')
            shot_type = seg.get('shot_type', '')
            timeline_segments += f'''
                <div class="timeline-segment {tier}" 
                     style="width: {seg_pct}%"
                     title="{shot_type} - {tier.upper()}"
                     data-start="{seg['start_time']:.1f}">
                </div>
            '''
        
        # Segments list HTML
        segments_html = ""
        for i, seg in enumerate(segments):
            tier = seg.get('tier', 'discard')
            shot_type = seg.get('shot_type', 'DESCONOCIDO')
            explanation = seg.get('explanation', {})
            evaluation = seg.get('evaluation', {})
            
            shot_type_names = {
                'ESTATICA': 'Toma estática',
                'PANEO': 'Paneo horizontal',
                'TILT': 'Tilt vertical',
                'MOVIMIENTO_FLUIDO': 'Movimiento fluido',
                'TRACKING': 'Seguimiento',
                'SHAKY': 'Inestable',
            }
            shot_name = shot_type_names.get(shot_type, shot_type)
            
            # Verificar si está borroso
            is_blurry = seg.get('is_blurry', False)
            blurry_tag = '<span class="blurry-tag">BORROSO</span>' if is_blurry else ''
            
            # Criterios
            criteria_html = ""
            for criterion in evaluation.get('criteria', []):
                icon_class = 'pass' if criterion.get('passed', False) else 'fail'
                icon = '✓' if criterion.get('passed', False) else '✗'
                criteria_html += f'''
                    <div class="criterion">
                        <div class="criterion-icon {icon_class}">{icon}</div>
                        <span class="criterion-name">{criterion.get('name', '')}</span>
                        <span class="criterion-value">{criterion.get('explanation', '')}</span>
                    </div>
                '''
            
            blurry_class = ' blurry' if is_blurry else ''
            segments_html += f'''
                <div class="segment-card{blurry_class}" data-tier="{tier}">
                    <div class="segment-header" onclick="toggleSegment(this)">
                        <div>
                            <span class="segment-badge {tier}">{tier.upper()}</span>
                            {blurry_tag}
                            <span class="shot-type-tag">{shot_name}</span>
                            <div class="segment-time">{format_time(seg['start_time'])} - {format_time(seg['end_time'])} ({seg['duration']:.1f}s)</div>
                        </div>
                        <div class="segment-score">{seg.get('score', 0):.1f}</div>
                    </div>
                    <div class="segment-details">
                        <div class="explanation-title">¿Por qué {tier.upper()}?</div>
                        <div class="criteria-list">
                            {criteria_html}
                        </div>
                    </div>
                </div>
            '''
        
        videos_html += f'''
            <div class="video-card">
                <div class="video-header" onclick="toggleVideo(this)">
                    <div>
                        <div class="video-name">{video['filename']}</div>
                        <div class="video-meta">{format_time(duration)} · {len(segments)} segmentos</div>
                    </div>
                    <div class="video-usable">{usable_pct:.0f}% usable</div>
                </div>
                <div class="video-details">
                    <div class="timeline">
                        <div class="timeline-bar">
                            {timeline_segments}
                        </div>
                    </div>
                    <div class="segments-list">
                        <div class="filter-bar">
                            <button class="filter-btn active" data-filter="all">Todos</button>
                            <button class="filter-btn" data-filter="gold">Gold</button>
                            <button class="filter-btn" data-filter="silver">Silver</button>
                            <button class="filter-btn" data-filter="bronze">Bronze</button>
                            <button class="filter-btn" data-filter="discard">Descartar</button>
                            <button class="filter-btn" data-filter="blurry">Borrosos</button>
                        </div>
                        {segments_html}
                    </div>
                </div>
            </div>
        '''
    
    # Stats
    total_dur = stats.get('total_duration', 0)
    gold_pct = stats.get('gold_pct', 0)
    silver_pct = stats.get('silver_pct', 0)
    bronze_pct = stats.get('bronze_pct', 0)
    discard_pct = stats.get('discard_pct', 0)
    usable_pct = stats.get('usable_pct', 0)
    
    # Shot types summary
    shot_types = stats.get('shot_types', {})
    shot_summary = ", ".join([f"{v} {k.lower()}" for k, v in shot_types.items()])
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Analyzer - Reporte Detallado</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Video Analyzer</h1>
            <p class="subtitle">{timestamp} · {stats.get('total_videos', 0)} videos · {stats.get('segment_count', 0)} segmentos</p>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_videos', 0)}</div>
                <div class="stat-label">Videos</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{format_time(total_dur)}</div>
                <div class="stat-label">Duración total</div>
            </div>
            <div class="stat-card">
                <div class="stat-value gold">{format_time(stats.get('gold_duration', 0))}</div>
                <div class="stat-label">Gold ({gold_pct:.0f}%)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value silver">{format_time(stats.get('silver_duration', 0))}</div>
                <div class="stat-label">Silver ({silver_pct:.0f}%)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value green">{usable_pct:.0f}%</div>
                <div class="stat-label">Usable</div>
            </div>
        </div>
        
        <div class="progress-bar">
            <div class="progress-bar-inner">
                <div class="progress-gold" style="width: {gold_pct}%"></div>
                <div class="progress-silver" style="width: {silver_pct}%"></div>
                <div class="progress-bronze" style="width: {bronze_pct}%"></div>
                <div class="progress-discard" style="width: {discard_pct}%"></div>
            </div>
        </div>
        
        <p class="section-title">Análisis por video</p>
        
        <input type="text" class="search-box" placeholder="Buscar video..." id="searchBox">
        
        {videos_html}
    </div>
    
    <script>
        function toggleVideo(header) {{
            const details = header.nextElementSibling;
            details.classList.toggle('open');
        }}
        
        function toggleSegment(header) {{
            const details = header.nextElementSibling;
            details.classList.toggle('open');
        }}
        
        // Filtros
        document.querySelectorAll('.filter-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                const parent = this.closest('.segments-list');
                parent.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                const filter = this.dataset.filter;
                parent.querySelectorAll('.segment-card').forEach(card => {{
                    if (filter === 'all') {{
                        card.style.display = 'block';
                    }} else if (filter === 'blurry') {{
                        card.style.display = card.classList.contains('blurry') ? 'block' : 'none';
                    }} else if (card.dataset.tier === filter) {{
                        card.style.display = 'block';
                    }} else {{
                        card.style.display = 'none';
                    }}
                }});
            }});
        }});
        
        // Búsqueda
        document.getElementById('searchBox').addEventListener('input', function() {{
            const query = this.value.toLowerCase();
            document.querySelectorAll('.video-card').forEach(card => {{
                const name = card.querySelector('.video-name').textContent.toLowerCase();
                card.style.display = name.includes(query) ? 'block' : 'none';
            }});
        }});
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def format_time(seconds):
    """Formatea segundos a string legible"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"
