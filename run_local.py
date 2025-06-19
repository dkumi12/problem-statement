# run_local.py
from flask import Flask, send_from_directory
from flask_cors import CORS
import os
import sys

# Add the api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

# Import the API blueprint from api/index.py
from api.index import api_bp

# Create a new Flask app for serving everything
app = Flask(__name__, static_folder='static')
CORS(app)

# Register the API blueprint
app.register_blueprint(api_bp, url_prefix='/api')

# Serve the frontend
@app.route('/')
def serve_frontend():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    print("🚀 Starting ProblemSprint AI server...")
    print("📍 Frontend: http://localhost:5000")
    print("📍 API: http://localhost:5000/api")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(debug=True, port=5000)