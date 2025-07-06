from flask import Flask, jsonify, request, render_template
from pymongo import MongoClient
import datetime
import os

# Initialize Flask
app = Flask(__name__, template_folder='templates')

# MongoDB setup
client = MongoClient('mongodb://localhost:27017/')
db = client['github_webhooks']

def format_event(event):
    """Format events as per assessment specs"""
    try:
        timestamp = datetime.datetime.fromisoformat(event["timestamp"]).strftime("%d %B %Y - %I:%M %p UTC")
        if event["action"] == "PUSH":
            return f'"{event["author"]}" pushed to "{event["to_branch"]}" on {timestamp}'
        elif event["action"] == "PULL_REQUEST":
            return f'"{event["author"]}" submitted a pull request from "{event["from_branch"]}" to "{event["to_branch"]}" on {timestamp}'
        elif event["action"] == "MERGE":
            return f'"{event["author"]}" merged branch "{event["from_branch"]}" to "{event["to_branch"]}" on {timestamp}'
    except Exception as e:
        print(f"Formatting error: {e}")
        return str(event)

@app.route('/')
def home():
    """Serve the frontend"""
    return render_template('index.html')

@app.route('/api/events', methods=['GET'])
def get_events():
    """Endpoint for UI polling"""
    try:
        events = list(db.events.find().sort("timestamp", -1))
        return jsonify([format_event(e) for e in events])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """GitHub webhook handler"""
    try:
        event_type = request.headers.get('X-GitHub-Event')
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        doc = {"timestamp": datetime.datetime.utcnow().isoformat()}

        if event_type == 'push':
            doc.update({
                "request_id": data.get('head_commit', {}).get('id'),
                "author": data.get('sender', {}).get('login'),
                "action": "PUSH",
                "from_branch": None,
                "to_branch": data.get('ref', '').replace('refs/heads/', '')
            })
        elif event_type == 'pull_request':
            pr = data.get('pull_request', {})
            doc.update({
                "request_id": str(pr.get('number')),
                "author": pr.get('user', {}).get('login'),
                "action": "MERGE" if pr.get('merged') else "PULL_REQUEST",
                "from_branch": pr.get('head', {}).get('ref'),
                "to_branch": pr.get('base', {}).get('ref')
            })
        else:
            return jsonify({"status": "ignored"}), 200

        db.events.insert_one(doc)
        return jsonify({"status": "success"})

    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
