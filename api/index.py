# api/index.py
from flask import Flask, Blueprint, request, jsonify
from flask_cors import CORS
import json
import requests
import os
from werkzeug.utils import secure_filename
import base64
from datetime import datetime

# Create a Blueprint instead of Flask app for better modularity
api_bp = Blueprint('api', __name__)

# Configuration
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'md'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file_content, filename):
    """Extract text from various file formats"""
    ext = filename.rsplit('.', 1)[1].lower()
    
    if ext in ['txt', 'md']:
        return file_content.decode('utf-8', errors='ignore')
    elif ext == 'pdf':
        # For PDF files, you would need PyPDF2 or similar
        # For now, returning a placeholder
        return f"[PDF content from {filename}]"
    elif ext in ['doc', 'docx']:
        # For Word files, you would need python-docx
        # For now, returning a placeholder
        return f"[Word document content from {filename}]"
    
    return f"[Content from {filename}]"

@api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@api_bp.route('/test', methods=['POST'])
def test_endpoint():
    data = request.json
    return jsonify({
        "success": True,
        "message": "Backend received your data!",
        "received": data
    })

@api_bp.route('/models', methods=['POST'])
def get_models():
    """Fetch available models from OpenRouter"""
    try:
        data = request.json
        api_key = data.get('apiKey')
        
        if not api_key:
            return jsonify({"error": "API key is required"}), 400
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'HTTP-Referer': request.headers.get('Referer', 'https://problemsprint-ai.vercel.app'),
            'X-Title': 'ProblemSprint AI'
        }
        
        response = requests.get(
            'https://openrouter.ai/api/v1/models',
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch models"}), 400
        
        models_data = response.json()
        
        # Format models for frontend
        models = []
        for model in models_data.get('data', []):
            # Extract pricing info safely
            pricing = model.get('pricing', {})
            if pricing is None:
                pricing = {}
            
            model_info = {
                'id': model['id'],
                'name': model.get('name', model['id']),
                'context_length': model.get('context_length', 4096),
                'pricing': {
                    'prompt': float(pricing.get('prompt', 0)) if pricing.get('prompt') else 0,
                    'completion': float(pricing.get('completion', 0)) if pricing.get('completion') else 0
                }
            }
            models.append(model_info)
        
        # Sort by name
        models.sort(key=lambda x: x['name'].lower())
        
        return jsonify({
            "success": True,
            "models": models
        })
        
    except Exception as e:
        return jsonify({"error": f"Error fetching models: {str(e)}"}), 500

@api_bp.route('/generate', methods=['POST'])
def generate_problem_statement():
    try:
        data = request.json
        api_key = data.get('apiKey')
        problem_description = data.get('problemDescription')
        attached_files = data.get('attachedFiles', [])
        selected_model = data.get('model', 'anthropic/claude-3.5-sonnet')  # Default to Claude
        
        if not api_key:
            return jsonify({"error": "API key is required"}), 400
        
        if not problem_description:
            return jsonify({"error": "Problem description is required"}), 400
        
        # Process attached files
        attached_context = ""
        if attached_files:
            attached_context = "\n\nATTACHED DOCUMENTS FOR CONTEXT:\n"
            for file_data in attached_files:
                filename = file_data.get('name', 'Unknown')
                content = file_data.get('content', '')
                
                if content:
                    # Decode base64 content
                    try:
                        file_content = base64.b64decode(content)
                        text_content = extract_text_from_file(file_content, filename)
                        attached_context += f"\n--- {filename} ---\n{text_content}\n"
                    except Exception as e:
                        print(f"Error processing file {filename}: {str(e)}")
        
        # Prepare the prompt
        prompt = f"""You are ProblemSprint AI, an expert at converting problem descriptions into well-defined AI problem statements.

The user has provided the following problem description:

{problem_description}{attached_context}

Analyze this description and extract:
1. The core pain point(s) or user frustrations
2. Any proposed ideas or solutions mentioned
3. Any data, metrics, or evidence provided

Then generate the following outputs:

1. PROBLEM STATEMENT (1 sentence): A clear, actionable problem statement that combines the pain point with a proposed solution approach.

2. SUCCESS METRIC (SMART format): A specific, measurable, achievable, relevant, and time-bound metric that will indicate success.

3. TRACEABILITY REPORT: Explain how you identified the pain points, ideas, and data from the user's description, and how these shaped the final problem statement and success metric.

4. BIAS CHECK: Identify any potential biases, assumptions, or limitations in the provided information that could affect the problem definition or solution approach.

Format your response as JSON with the following structure:
{{
    "problemStatement": "...",
    "successMetric": "...",
    "traceabilityReport": "...",
    "biasCheck": {{
        "hasBias": true/false,
        "description": "...",
        "recommendations": ["..."]
    }}
}}"""

        # Call OpenRouter API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'HTTP-Referer': request.headers.get('Referer', 'https://problemsprint-ai.vercel.app'),
            'X-Title': 'ProblemSprint AI'
        }
        
        payload = {
            'model': selected_model,
            'messages': [{
                'role': 'user',
                'content': prompt
            }],
            'temperature': 0.7,
            'max_tokens': 1000
        }
        
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            error_data = response.json()
            return jsonify({"error": error_data.get('error', {}).get('message', 'API request failed')}), 400
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Parse JSON from response
        try:
            json_match = content[content.find('{'):content.rfind('}')+1]
            output = json.loads(json_match)
        except:
            # If JSON parsing fails, try to extract information manually
            output = {
                "problemStatement": "Unable to parse structured response from this model.",
                "successMetric": "Please try with a different model that supports JSON responses.",
                "traceabilityReport": f"Model {selected_model} may not support structured JSON output.",
                "biasCheck": {
                    "hasBias": False,
                    "description": "Could not perform bias check due to parsing issues.",
                    "recommendations": ["Try using Claude, GPT-4, or other models that support JSON formatting."]
                }
            }
            # Try to include the raw response for debugging
            if len(content) < 500:
                output["rawResponse"] = content
        
        return jsonify({
            "success": True,
            "output": output,
            "timestamp": datetime.now().isoformat()
        })
        
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response"}), 500
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@api_bp.route('/export', methods=['POST'])
def export_data():
    try:
        data = request.json
        export_format = data.get('format', 'json')
        output_data = data.get('data')
        
        if not output_data:
            return jsonify({"error": "No data to export"}), 400
        
        if export_format == 'markdown':
            markdown = generate_markdown(output_data)
            return jsonify({
                "success": True,
                "content": markdown,
                "filename": f"problemsprint-{int(datetime.now().timestamp())}.md"
            })
        else:
            return jsonify({
                "success": True,
                "content": json.dumps(output_data, indent=2),
                "filename": f"problemsprint-{int(datetime.now().timestamp())}.json"
            })
            
    except Exception as e:
        return jsonify({"error": f"Export error: {str(e)}"}), 500

def generate_markdown(data):
    inputs = data.get('inputs', {})
    outputs = data.get('outputs', {})
    
    markdown = f"""# ProblemSprint AI Output

## Input

### Problem Description
{inputs.get('problemDescription', 'N/A')}

"""
    
    if inputs.get('model'):
        markdown += f"""### AI Model Used
{inputs.get('model')}

"""
    
    if inputs.get('attachedFiles'):
        markdown += f"""### Attached Files
{chr(10).join(['- ' + f for f in inputs.get('attachedFiles', [])])}

"""
    
    markdown += f"""## Generated Outputs

### Problem Statement
{outputs.get('problemStatement', 'N/A')}

### Success Metric (SMART Format)
{outputs.get('successMetric', 'N/A')}

### Traceability Report
{outputs.get('traceabilityReport', 'N/A')}

### Bias Check
{outputs.get('biasCheck', {}).get('description', 'N/A')}

"""
    
    recommendations = outputs.get('biasCheck', {}).get('recommendations', [])
    if recommendations:
        markdown += "#### Recommendations\n"
        for i, rec in enumerate(recommendations):
            markdown += f"{i + 1}. {rec}\n"
        markdown += "\n"
    
    markdown += f"""---
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return markdown

# For Vercel deployment only - create app at the end
app = Flask(__name__)
CORS(app)
app.register_blueprint(api_bp)