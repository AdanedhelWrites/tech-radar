"""
Flask Web Application - Cybersecurity News Scraper
Cache-based, no file storage
"""

import logging
import os
import json
from datetime import datetime

from flask import Flask, render_template, jsonify, request
from flask_caching import Cache
from scraper_multi import MultiSourceScraper

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cache configuration
if os.environ.get('CACHE_TYPE') == 'redis':
    cache = Cache(app, config={
        'CACHE_TYPE': 'RedisCache',
        'CACHE_REDIS_URL': os.environ.get('CACHE_REDIS_URL', 'redis://localhost:6379/0'),
        'CACHE_DEFAULT_TIMEOUT': int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 3600))
    })
else:
    # Simple in-memory cache for development
    cache = Cache(app, config={
        'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 3600
    })

CACHE_KEY_NEWS = 'cybersecurity_news'
CACHE_KEY_TIMESTAMP = 'last_update'

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')

@app.route('/api/news')
@cache.cached(timeout=300, key_prefix=CACHE_KEY_NEWS)
def get_news():
    """Haberleri getir (cache'den)"""
    news_data = cache.get(CACHE_KEY_NEWS)
    if news_data:
        return jsonify({
            'success': True,
            'data': news_data,
            'cached': True,
            'count': len(news_data)
        })
    
    return jsonify({
        'success': False,
        'message': 'Cache bos. Lutfen once haberleri cekin.',
        'data': [],
        'count': 0
    })

@app.route('/api/fetch', methods=['POST'])
def fetch_news():
    """Yeni haberleri cek"""
    try:
        data = request.get_json()
        days = data.get('days', 7)
        selected_sources = data.get('sources', None)
        
        scraper = MultiSourceScraper()
        articles = scraper.fetch_all_news(days=days, selected_sources=selected_sources)
        
        if articles:
            processed = scraper.process_news(articles)
            
            # Cache'e kaydet
            cache.set(CACHE_KEY_NEWS, processed)
            cache.set(CACHE_KEY_TIMESTAMP, datetime.now().isoformat())
            
            return jsonify({
                'success': True,
                'message': f'{len(processed)} haber basariyla cekildi',
                'data': processed,
                'count': len(processed)
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Haber bulunamadi',
                'data': [],
                'count': 0
            })
            
    except Exception:
        logger.exception('fetch_news basarisiz')
        return jsonify({
            'success': False,
            'message': 'Islem sirasinda sunucuda beklenmeyen bir hata olustu.',
            'data': [],
            'count': 0
        }), 500

@app.route('/api/clear', methods=['POST'])
def clear_cache():
    """Cache'i temizle"""
    cache.delete(CACHE_KEY_NEWS)
    cache.delete(CACHE_KEY_TIMESTAMP)
    return jsonify({
        'success': True,
        'message': 'Cache basariyla temizlendi'
    })

@app.route('/api/stats')
def get_stats():
    """Istatistikleri getir"""
    news_data = cache.get(CACHE_KEY_NEWS) or []
    timestamp = cache.get(CACHE_KEY_TIMESTAMP)
    
    # Kaynaklara gore dagilim
    source_count = {}
    for article in news_data:
        source = article.get('source', 'Bilinmiyor')
        source_count[source] = source_count.get(source, 0) + 1
    
    return jsonify({
        'success': True,
        'total': len(news_data),
        'by_source': source_count,
        'last_update': timestamp,
        'cached': len(news_data) > 0
    })

@app.route('/api/export')
def export_news():
    """Haberleri JSON olarak disari aktar"""
    news_data = cache.get(CACHE_KEY_NEWS) or []
    
    return jsonify({
        'success': True,
        'data': news_data,
        'exported_at': datetime.now().isoformat(),
        'count': len(news_data)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
