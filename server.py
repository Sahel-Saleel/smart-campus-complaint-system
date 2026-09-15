from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import os
import requests

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

# Optional: Add your own summarization endpoint
@app.route('/api/summarize', methods=['POST'])
def summarize():
    data = request.json
    text = data.get('text', '')
    length = data.get('length', 'medium')
    
    # You can integrate with a real summarization API here
    # For example, using Hugging Face, OpenAI, etc.
    
    # Simple local summarization (you can replace with actual API)
    sentences = text.split('.')
    if length == 'short':
        summary = '. '.join(sentences[:3]) + '.'
    elif length == 'medium':
        summary = '. '.join(sentences[:5]) + '.'
    else:
        summary = '. '.join(sentences[:8]) + '.'
    
    return jsonify({'summary': summary})

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    print("="*50)
    print("Text to Voice Converter with Summarizer")
    print("="*50)
    print("\n🚀 Server starting...")
    print("📁 Serving files from current directory")
    print("\n🌐 Open this URL in your browser:")
    print("   http://localhost:5000")
    print("\n✨ New Features:")
    print("   📊 Text Summarization")
    print("   🔁 Sentence Repetition")
    print("   📖 Dictionary & Synonyms")
    print("   🔊 Text to Speech")
    print("\n⚠️  Press CTRL+C to stop the server")
    print("="*50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)