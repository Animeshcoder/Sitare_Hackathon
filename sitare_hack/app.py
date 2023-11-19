from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
import cv2
import numpy as np
import os
from datetime import datetime
import pytz
import base64
import dlib
from sqlalchemy.sql import extract


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db = SQLAlchemy(app)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    photo_path = db.Column(db.String(300))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    subject = db.Column(db.String(100))
    date = db.Column(db.Date, default=datetime.now(pytz.timezone('Asia/Kolkata')))
    __table_args__ = (db.UniqueConstraint('student_id', 'subject', 'date', name='uix_1'), )


with app.app_context():
    db.create_all()

def detect_face(image):
    detector = dlib.get_frontal_face_detector()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = detector(gray)
    
    if len(faces) > 0:
        face = faces[0]
        x = face.left()
        y = face.top()
        w = face.right() - x
        h = face.bottom() - y
        roi_gray = gray[y:y+h, x:x+w]
        return roi_gray
    else:
        return None

def resize_image(image):
    return cv2.resize(image, (150, 150))

def convert_to_gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def convert_to_rgb(image):
    return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

def face_comparison(image1, image2):
    face_recognition_model = dlib.face_recognition_model_v1('C:/Users/Animesh/Downloads/dlib_face_recognition_resnet_model_v1.dat/dlib_face_recognition_resnet_model_v1.dat')
    image1_embedding = face_recognition_model.compute_face_descriptor(image1)
    image2_embedding = face_recognition_model.compute_face_descriptor(image2)
    dist = np.linalg.norm(np.array(image1_embedding) - np.array(image2_embedding))
    
    return dist < 0.8

@app.route('/')
def index():
    return render_template('index.html')
from io import BytesIO
from PIL import Image

@app.route('/student', methods=['GET', 'POST'])
def student():
    if request.method == 'POST':
        id = request.form['id']
        student = db.session.query(Student).filter_by(id=id).first()
        
        if student:
            return 'Student exists'
        else:
            return 'No student found'
    
    return render_template('student.html')

@app.route('/process_image', methods=['POST'])
def process_image():
    if request.method == 'POST':
        id = request.form['id']
        image_data = request.form['image']
        
        header, image_data = image_data.split(';base64,')
        image_data = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_data))
        image_np = np.array(image)
        student = db.session.query(Student).filter_by(id=id).first()
        if student and image_np is not None:
            stored_photo = cv2.imread(student.photo_path)
            face = convert_to_gray(image_np)
            stored_face = convert_to_gray(stored_photo)
            face = convert_to_rgb(face)
            stored_face = convert_to_rgb(stored_face)
            face = resize_image(face)
            stored_face = resize_image(stored_face)
            if face is not None and stored_face is not None:
                match = face_comparison(face, stored_face)
                if match:
                    try:
                        existing_attendance = db.session.query(Attendance).filter_by(student_id=student.id, date=datetime.now(pytz.timezone('Asia/Kolkata')), subject=request.form['subject']).first()
                        if existing_attendance:
                            return 'Attendance already marked for this subject today'
                        attendance = Attendance(student_id=student.id, subject=request.form['subject'])
                        db.session.add(attendance)
                        db.session.commit()
                        return 'Attendance marked'
                    except sqlalchemy.exc.IntegrityError:
                        db.session.rollback()
                        return 'Attendance already marked for this subject today'
                else:
                    return 'Face does not match'
            else:
                return 'Face not detected'
        else:
            return 'No image received or invalid student ID'
        
    return render_template('student.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'check_attendance':
            id = request.form['id']
            current_month = datetime.now().month
            attendance_records = db.session.query(Attendance).filter_by(student_id=id).filter(extract('month', Attendance.date) == current_month).all()
            subjects = set([record.subject for record in attendance_records])
            attendance_table = {subject: len([record for record in attendance_records if record.subject == subject]) for subject in subjects}
            return render_template('attendance.html', attendance_table=attendance_table)

        elif action == 'add_student':
            id = request.form['id']
            photo = request.files['photo']
            if not os.path.exists('photos'):
                os.makedirs('photos')
            photo_path = os.path.join('photos', photo.filename)
            photo.save(photo_path)
            new_student = Student(id=id, photo_path=photo_path)
            db.session.add(new_student)
            db.session.commit()
            return 'New student added'
    return render_template('admin.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['user']
        password = request.form['password']
        users = {
            'section': {
                'user': 'user1',
                'password': 'password1'
            }
        }
        if user == users['section']['user'] and password == users['section']['password']:
            return render_template('admin.html')
        else:
            error = 'Invalid username or password'
            return render_template('login.html', error=error)
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
