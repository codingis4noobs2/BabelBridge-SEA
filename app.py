from flask import Flask, render_template, request, redirect, url_for, flash, session
from faker import Faker
import random
import os
from werkzeug.utils import secure_filename
import assemblyai as aai
import fitz
from docx import Document
import requests
import dotenv

aai.settings.api_key = os.getenv('API_KEY')
app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/uploads'
PENDING_FOLDER = 'static/pending_approvals'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'mp3', 'mp4'}
pending_approvals = {}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PENDING_FOLDER'] = PENDING_FOLDER

users_db = {
    'contributor1': {'password': 'pass1', 'score': 0, 'role': 'contributor'},
    'contributor2': {'password': 'pass2', 'score': 0, 'role': 'contributor'},
    'contributor3': {'password': 'pass3', 'score': 0, 'role': 'contributor'},
    'contributor4': {'password': 'pass4', 'score': 0, 'role': 'contributor'},
    'user1': {'password': 'pass1', 'score': 10, 'role': 'user'}
}

fake = Faker()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_random_participants(num=10):
    participants = []
    for _ in range(num):
        username = fake.user_name()
        while username in users_db or any(username == u[0] for u in participants):
            username = fake.user_name()
        score = random.randint(1, 10)
        participants.append((username, {'score': score, 'role': 'user'}))
    return participants

def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_docx(docx_path):
    doc = Document(docx_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

@app.route('/show_text/<filename>')
def show_text(filename):
    file_path = os.path.join(app.config['PENDING_FOLDER'], filename)
    if filename.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    elif filename.endswith('.doc') or filename.endswith('.docx'):
        text = extract_text_from_docx(file_path)
    else:
        text = "File format not supported for text extraction."
    return render_template('show_text.html', text=text, filename=filename, username=session.get('username'), score=session.get('score'), role=session.get('role'))

@app.route('/transcribe/<filename>')
def transcribe(filename):
    file_path = os.path.join(app.config['PENDING_FOLDER'], filename)
    if filename.endswith('.mp3') or filename.endswith('.mp4') or filename.endswith('.wav'):
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(file_path)
        text = transcript.text if transcript else "Transcription failed or not available."
    else:
        text = "File format not supported for transcription."
    return render_template('transcribe_result.html', text=text, filename=filename, username=session.get('username'), score=session.get('score'), role=session.get('role'))

@app.route('/')
def home():
    return render_template('index.html', username=session.get('username'), score=session.get('score'), role=session.get('role'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_db.get(username)
        if user and user['password'] == password:
            session['username'] = username
            session['score'] = user['score']
            session['role'] = user['role']
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!')
    return render_template('login.html')

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form['username']
    password = request.form['password']
    if username not in users_db:
        users_db[username] = {'password': password, 'score': 0, 'role': 'user'}
        session['username'] = username
        session['score'] = 0
        session['role'] = 'user'
        flash('Account created successfully!', 'success')
    else:
        flash('Username already exists!', 'danger')
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('score', None)
    session.pop('role', None)
    return redirect(url_for('home'))

@app.route('/leaderboard')
def leaderboard():
    random_participants = generate_random_participants(num=10)
    combined_participants = list(users_db.items()) + random_participants
    top_participants = sorted(combined_participants, key=lambda user: user[1]['score'], reverse=True)[:10]
    return render_template('leaderboard.html', participants=top_participants, username=session.get('username'), score=session.get('score'), role=session.get('role'))

@app.route('/learn')
def learn():
    return render_template('learn.html', username=session.get('username', None), score=session.get('score'), role=session.get('role'))

@app.route('/our-mission')
def our_mission():
    return render_template('our_mission.html', username=session.get('username'), score=session.get('score'), role=session.get('role'))

@app.route('/store')
def store():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    username = session.get('username')
    score = session.get('score', 0)
    coins = score // 5
    items = [
        {'name': 'Camera1', 'cost': 4, 'img': 'cam1.jpg'},
        {'name': 'Camera2', 'cost': 9, 'img': 'cam2.jpg'},
        {'name': 'Camera3', 'cost': 2, 'img': 'cam3.jpg'}
    ]
    return render_template('store.html', username=username, score=session.get('score'), coins=coins, items=items)

@app.route('/contribute', methods=['GET', 'POST'])
def contribute():
    if 'username' not in session:
        flash('Please login to contribute.', 'warning')
        return redirect(url_for('login_page'))
    if request.method == 'POST':
        input_type = request.form['inputType']
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['PENDING_FOLDER'], filename)
            file.save(save_path)
            pending_approvals[filename] = {
                'submitter': session['username'],
                'votes': 0,
                'voters': set(),
                'path': save_path
            }
            flash('Successfully uploaded your contribution for approval!', 'success')
        else:
            flash('Invalid file type.', 'danger')
        return redirect(url_for('contribute'))
    return render_template('contribute.html', username=session.get('username'), score=session.get('score'), role=session.get('role'))

@app.route('/pending-approvals')
def pending_approvals_view():
    if 'username' not in session or session.get('role') != 'contributor':
        flash('Access restricted to contributors.', 'danger')
        return redirect(url_for('home'))
    return render_template('pending_approvals.html', files=pending_approvals, username=session.get('username'), score=session.get('score'), role=session.get('role'))

@app.route('/vote', methods=['POST'])
def vote():
    if 'username' not in session or session.get('role') != 'contributor':
        return 'Access Denied', 403
    filename = request.form['filename']
    vote_type = request.form['vote_type']
    voter = session['username']
    file_info = pending_approvals.get(filename)
    if file_info and voter not in file_info['voters']:
        if vote_type == 'approve':
            file_info['votes'] += 1
            file_info['voters'].add(voter)
            if file_info['votes'] >= 3:
                new_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.rename(file_info['path'], new_path)
                submitter = file_info['submitter']
                if submitter in users_db:
                    users_db[submitter]['score'] += 2
                del pending_approvals[filename]
                flash(f'File {filename} approved and moved to uploads.', 'success')
    elif voter in file_info['voters']:
        flash('You have already voted on this file.', 'info')
    else:
        flash('File does not exist.', 'danger')

    return redirect(url_for('pending_approvals_view'))

@app.route('/public_dataset')
def public_dataset():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('public_dataset.html', files=files, username=session.get('username'), score=session.get('score'), role=session.get('role'))

if __name__ == '__main__':
    app.run(debug=True)