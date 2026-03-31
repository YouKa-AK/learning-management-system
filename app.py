from flask import Flask, render_template, request, session, redirect, url_for
import mysql.connector
import os
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = "secretkey"

# 📂 Upload folders
SUBMISSION_FOLDER = 'uploads/submissions'
MATERIAL_FOLDER = 'uploads/materials'

# 📁 Allowed file types
ALLOWED_EXTENSIONS = {'pdf','doc','docx','txt','zip','png','jpg','ppt','pptx'}

# ⚙️ Config
app.config['SUBMISSION_FOLDER'] = SUBMISSION_FOLDER
app.config['MATERIAL_FOLDER'] = MATERIAL_FOLDER

# 📁 Create folders if not exist
os.makedirs(SUBMISSION_FOLDER, exist_ok=True)
os.makedirs(MATERIAL_FOLDER, exist_ok=True)


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",      
        database="lms_db",
        port=3307
    )

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def login():
    message = ""
    status = ""

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, role FROM users WHERE email=%s AND password=%s",
            (email, password)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['role'] = user[1]
            session['email'] = email

            if user[1] == "teacher":
                return redirect('/teacher_dashboard')
            
            elif user[1] == "student":
                return redirect('/student_dashboard')

        else:
            message = "Invalid Email or Password"
            status = "error"

    return render_template('login.html', message=message, status=status)


@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ""
    status = ""

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        emp_code = request.form['empCode']
        password = request.form['password']

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                message = "Email already registered"
                status = "error"
            else:
                # Insert into teacher table
                cursor.execute(
                    "INSERT INTO teacher (name, email, emp_code, password) VALUES (%s, %s, %s, %s)",
                    (name, email, emp_code, password)
                )

                # Insert into users table
                cursor.execute(
                    "INSERT INTO users (email, password, role) VALUES (%s, %s, %s)",
                    (email, password, "teacher")
                )

                conn.commit()   # 🔥 IMPORTANT

                message = "Registration Successful!"
                status = "success"

        except Exception as e:
            print("ERROR:", e)   # 🔥 THIS WILL SHOW REAL ISSUE
            message = "Something went wrong"
            status = "error"

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('register.html', message=message, status=status)

@app.route('/teacher_dashboard')
def teacher_dashboard():

    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM teacher WHERE email=%s", (session['email'],))
    teacher = cursor.fetchone()

    cursor.close()
    conn.close()

    teacher_name = teacher[0] if teacher else "Teacher"

    return render_template('teacher_dashboard.html', teacher_name=teacher_name)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/create_course', methods=['GET', 'POST'])
def create_course():

    if 'user_id' not in session:
        return redirect('/')

    if request.method == 'POST':
        course_name = request.form.get('course_name')
        course_code = request.form.get('course_code')
        teacher_email = session.get('email')

        if not course_name or not course_code:
            return "All fields required"

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO courses (course_name, course_code, teacher_email) VALUES (%s, %s, %s)",
            (course_name, course_code, teacher_email)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return redirect('/teacher_dashboard')

    return render_template('create_course.html')

@app.route('/view_my_courses')
def view_my_courses():

    if 'user_id' not in session or 'email' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            c.id,
            c.course_name,
            c.course_code,
            COUNT(e.id) AS student_count
        FROM courses c
        LEFT JOIN enrollments e ON c.id = e.course_id
        WHERE c.teacher_email = %s
        GROUP BY c.id
    """, (session['email'],))

    courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('view_my_courses.html', courses=courses)

@app.route('/delete_course/<int:course_id>')
def delete_course(course_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # First delete enrollments (important to avoid foreign key errors)
    cursor.execute("DELETE FROM enrollments WHERE course_id = %s", (course_id,))

    # Then delete course
    cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/view_my_courses')

@app.route('/enroll_page/<int:course_id>')
def enroll_page(course_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get course name
    cursor.execute("SELECT course_name FROM courses WHERE id=%s", (course_id,))
    course = cursor.fetchone()

    # Get class-wise student count
    cursor.execute("""
        SELECT class, COUNT(*) AS total_students
        FROM student
        GROUP BY class
    """)

    classes = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'enroll_student.html',
        course_id=course_id,
        course_name=course['course_name'],
        classes=classes
    )

@app.route('/enroll_student/<int:course_id>', methods=['POST'])
def enroll_student(course_id):

    if 'user_id' not in session:
        return redirect('/')

    student_emails = request.form.getlist('student_email[]')

    conn = get_db_connection()
    cursor = conn.cursor()

    for email in student_emails:
        cursor.execute(
            "INSERT INTO enrollments (course_id, student_email) VALUES (%s, %s)",
            (course_id, email)
        )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/view_my_courses')

@app.route('/enroll_class/<int:course_id>', methods=['POST'])
def enroll_class(course_id):

    if 'user_id' not in session:
        return redirect('/')

    selected_classes = request.form.getlist('classes[]')

    if not selected_classes:
        return "Please select at least one class"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch students from selected classes
    format_strings = ','.join(['%s'] * len(selected_classes))
    query = f"SELECT email FROM student WHERE class IN ({format_strings})"

    cursor.execute(query, tuple(selected_classes))
    students = cursor.fetchall()

    count = 0

    for student in students:

        # Avoid duplicate enrollment
        cursor.execute(
            "SELECT * FROM enrollments WHERE course_id=%s AND student_email=%s",
            (course_id, student[0])
        )

        exists = cursor.fetchone()

        if not exists:
            cursor.execute(
                "INSERT INTO enrollments (course_id, student_email) VALUES (%s, %s)",
                (course_id, student[0])
            )
            count += 1

    conn.commit()
    cursor.close()
    conn.close()

    from flask import flash, redirect, url_for

    flash(f"{count} students enrolled successfully!", "success")
    return redirect('/view_my_courses')

@app.route('/view_students/<int:course_id>')
def view_students(course_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get course name
    cursor.execute(
        "SELECT course_name FROM courses WHERE id=%s",
        (course_id,)
    )
    course = cursor.fetchone()

    # Get enrolled students
    cursor.execute(
        "SELECT id, student_email FROM enrollments WHERE course_id=%s",
        (course_id,)
    )
    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'view_students.html',
        course_name=course['course_name'],
        students=students,
        course_id=course_id
    )

@app.route('/remove_student/<int:enrollment_id>/<int:course_id>')
def remove_student(enrollment_id, course_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM enrollments WHERE id=%s",
        (enrollment_id,)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(f'/view_students/{course_id}')

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():

    message = ""
    status = ""

    if request.method == 'POST':
        name = request.form['name']
        student_class = request.form['class']
        roll_number = request.form['roll_number']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check duplicate email
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            message = "Email already registered"
            status = "error"
        else:
            # Insert into student table
            cursor.execute(
                """INSERT INTO student 
                   (name, class, roll_number, email, password) 
                   VALUES (%s, %s, %s, %s, %s)""",
                (name, student_class, roll_number, email, password)
            )

            # Insert into users table
            cursor.execute(
                "INSERT INTO users (email, password, role) VALUES (%s, %s, %s)",
                (email, password, "student")
            )

            conn.commit()
            message = "Registration Successful!"
            status = "success"

        cursor.close()
        conn.close()

    return render_template('student_register.html', message=message, status=status)

@app.route('/student_dashboard')
def student_dashboard():

    if 'user_id' not in session or session['role'] != 'student':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT name FROM student WHERE email=%s",
        (session['email'],)
    )

    student = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        'student_dashboard.html',
        student_name=student['name']
    )

@app.route('/my_courses')
def my_courses():

    if 'user_id' not in session or session['role'] != 'student':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.id, c.course_name, c.course_code, c.teacher_email
        FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_email = %s
    """,(session['email'],))

    courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('my_courses.html',courses=courses)

@app.route('/create_assignment/<int:course_id>', methods=['GET','POST'])
def create_assignment(course_id):

    if 'user_id' not in session or session['role']!='teacher':
        return redirect('/')

    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)

    cursor.execute("SELECT course_name FROM courses WHERE id=%s",(course_id,))
    course=cursor.fetchone()

    if request.method=='POST':

        title=request.form['title']
        description=request.form['description']
        due_date=request.form['due_date']
        max_marks=request.form.get('max_marks',100)

        cursor.execute(
            "INSERT INTO assignments (course_id,title,description,due_date,max_marks) VALUES (%s,%s,%s,%s,%s)",
            (course_id,title,description,due_date,max_marks)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(f'/view_assignments/{course_id}')

    cursor.close()
    conn.close()

    return render_template('create_assignment.html',course=course,course_id=course_id)

@app.route('/view_assignments/<int:course_id>')
def view_assignments(course_id):

    if 'user_id' not in session:
        return redirect('/')

    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)

    cursor.execute("SELECT id,course_name FROM courses WHERE id=%s",(course_id,))
    course=cursor.fetchone()

    cursor.execute(
        "SELECT * FROM assignments WHERE course_id=%s ORDER BY due_date ASC",
        (course_id,)
    )

    assignments=cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'view_assignments.html',
        assignments=assignments,
        course=course,
        role=session['role']
    )

@app.route('/submit_assignment/<int:assignment_id>', methods=['GET','POST'])
def submit_assignment(assignment_id):

    if 'user_id' not in session or session['role'] != 'student':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)   # ✅ IMPORTANT FIX

    # Get assignment
    cursor.execute(
        "SELECT a.*, c.course_name FROM assignments a JOIN courses c ON a.course_id=c.id WHERE a.id=%s",
        (assignment_id,)
    )
    assignment = cursor.fetchone()

    message = None
    status = None

    if request.method == 'POST':

        file = request.files.get('file')

        if file and allowed_file(file.filename):

            filename = secure_filename(f"{session['email']}_{assignment_id}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            file.save(file_path)

            # Check existing submission
            cursor.execute(
                "SELECT * FROM submissions WHERE assignment_id=%s AND student_email=%s",
                (assignment_id, session['email'])
            )
            existing = cursor.fetchone()

            if existing:
                # 🔁 UPDATE (re-upload)
                cursor.execute(
                    "UPDATE submissions SET file_path=%s, submitted_at=NOW() WHERE id=%s",
                    (file_path, existing['id'])
                )
                message = "Assignment re-submitted successfully!"
            else:
                # 🆕 INSERT
                cursor.execute(
                    "INSERT INTO submissions (assignment_id, student_email, file_path) VALUES (%s,%s,%s)",
                    (assignment_id, session['email'], file_path)
                )
                message = "Assignment submitted successfully!"

            conn.commit()
            status = "success"

        else:
            message = "Invalid file!"
            status = "error"

    # Fetch latest submission
    cursor.execute(
        "SELECT * FROM submissions WHERE assignment_id=%s AND student_email=%s",
        (assignment_id, session['email'])
    )
    existing = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        'submit_assignment.html',
        assignment=assignment,
        existing=existing,
        message=message,
        status=status
    )

@app.route('/view_submissions/<int:assignment_id>')
def view_submissions(assignment_id):

    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.*, u.email as student_email, g.marks, g.feedback
        FROM submissions s
        JOIN users u ON s.student_id = u.id
        LEFT JOIN grades g ON s.id = g.submission_id
        WHERE s.assignment_id = %s
    """, (assignment_id,))

    submissions = cursor.fetchall()

    # Get assignment details
    cursor.execute("SELECT * FROM assignments WHERE id=%s", (assignment_id,))
    assignment = cursor.fetchone()

    return render_template(
        'view_submissions.html',
        submissions=submissions,
        assignment=assignment,
        assignment_id=assignment_id
    )

@app.route('/my_grades')
def my_grades():

    if 'user_id' not in session or session['role']!='student':
        return redirect('/')

    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.title,a.due_date,a.max_marks,
        c.course_name,
        g.marks,g.feedback,
        s.submitted_at,s.file_path
        FROM submissions s
        JOIN assignments a ON s.assignment_id=a.id
        JOIN courses c ON a.course_id=c.id
        LEFT JOIN grades g ON s.id=g.submission_id
        WHERE s.student_email=%s
        ORDER BY s.submitted_at DESC
    """,(session['email'],))

    grades=cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('my_grades.html',grades=grades)

@app.route('/create_announcement/<int:course_id>', methods=['GET', 'POST'])
def create_announcement(course_id):

    # Only logged-in users
    if 'user_id' not in session:
        return redirect('/')

    # Only teacher can create announcement
    if session.get('role') != 'teacher':
        return "Access Denied"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get course info
    cursor.execute("SELECT * FROM courses WHERE id=%s", (course_id,))
    course = cursor.fetchone()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        # Insert announcement
        cursor.execute(
            "INSERT INTO announcements (course_id, teacher_email, title, content) VALUES (%s, %s, %s, %s)",
            (course_id, session['email'], title, content)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(f'/view_announcements/{course_id}')

    cursor.close()
    conn.close()

    return render_template(
        'create_announcement.html',
        course=course,
        course_id=course_id
    )

@app.route('/view_announcements/<int:course_id>')
def view_announcements(course_id):

    if 'user_id' not in session:
        return redirect('/')

    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)

    cursor.execute("SELECT id,course_name FROM courses WHERE id=%s",(course_id,))
    course=cursor.fetchone()

    cursor.execute(
        "SELECT * FROM announcements WHERE course_id=%s ORDER BY created_at DESC",
        (course_id,)
    )

    announcements=cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'view_announcements.html',
        announcements=announcements,
        course=course,
        role=session['role']
    )

@app.route('/delete_announcement/<int:announcement_id>/<int:course_id>')
def delete_announcement(announcement_id, course_id):

    if 'user_id' not in session:
        return redirect('/')

    # Optional: only teacher can delete
    if session.get('role') != 'teacher':
        return "Access Denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM announcements WHERE id = %s",
        (announcement_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(f'/view_announcements/{course_id}')

@app.route('/discussions/<int:course_id>', methods=['GET', 'POST'])
def discussions(course_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get course details
    cursor.execute("SELECT id, course_name FROM courses WHERE id=%s", (course_id,))
    course = cursor.fetchone()

    # Add new post
    if request.method == 'POST':
        content = request.form['content']
        parent_id = request.form.get('parent_id') or None

        cursor.execute(
            "INSERT INTO discussions (course_id, author_email, content, parent_id) VALUES (%s, %s, %s, %s)",
            (course_id, session['email'], content, parent_id)
        )
        conn.commit()

    # Get main posts
    cursor.execute("""
        SELECT d.*, 
               COALESCE(t.name, s.name, d.author_email) AS author_name
        FROM discussions d
        LEFT JOIN teacher t ON d.author_email = t.email
        LEFT JOIN student s ON d.author_email = s.email
        WHERE d.course_id=%s AND d.parent_id IS NULL
        ORDER BY d.created_at DESC
    """, (course_id,))
    
    posts = cursor.fetchall()

    # Get replies
    for post in posts:
        cursor.execute("""
            SELECT d.*, 
                   COALESCE(t.name, s.name, d.author_email) AS author_name
            FROM discussions d
            LEFT JOIN teacher t ON d.author_email = t.email
            LEFT JOIN student s ON d.author_email = s.email
            WHERE d.parent_id=%s
            ORDER BY d.created_at ASC
        """, (post['id'],))

        post['replies'] = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
    'discussions.html',
    posts=posts,
    course=course,
    course_id=course_id,
    role=session.get('role'),        
    current_user=session.get('email')  
    )  

@app.route('/delete_post/<int:post_id>/<int:course_id>')
def delete_post(post_id, course_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete replies first (important for foreign key)
    cursor.execute("DELETE FROM discussions WHERE parent_id = %s", (post_id,))

    # Delete main post
    cursor.execute("DELETE FROM discussions WHERE id = %s", (post_id,))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(f'/discussions/{course_id}') 

@app.route('/upload_material/<int:course_id>', methods=['GET', 'POST'])
def upload_material(course_id):

    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        title = request.form['title']
        material_type = request.form['type']

        file_path = None
        content = None

        # 📁 FILE UPLOAD
        if material_type == 'file':
            file = request.files['file']

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)

                filepath = os.path.join(app.config['MATERIAL_FOLDER'], filename)
                file.save(filepath)

                file_path = filepath

        # 🔗 LINK
        elif material_type == 'link':
            content = request.form['link']

        # 📝 TEXT
        elif material_type == 'text':
            content = request.form['text']

        cursor.execute("""
            INSERT INTO materials (course_id, title, type, content, file_path)
            VALUES (%s, %s, %s, %s, %s)
        """, (course_id, title, material_type, content, file_path))

        conn.commit()

        return redirect(url_for('view_materials', course_id=course_id))

    return render_template('upload_material.html', course_id=course_id)

@app.route('/view_materials/<int:course_id>')
def view_materials(course_id):

    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM materials
        WHERE course_id = %s
        ORDER BY id DESC
    """, (course_id,))

    materials = cursor.fetchall()

    return render_template(
        'view_materials.html',
        materials=materials,
        course_id=course_id
    )

@app.route('/edit_material/<int:material_id>', methods=['POST'])
def edit_material(material_id):

    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect('/')

    title = request.form['title']
    content = request.form.get('content')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE materials
        SET title = %s, content = %s
        WHERE id = %s
    """, (title, content, material_id))

    conn.commit()
    conn.close()

    return redirect(request.referrer)

@app.route('/delete_material/<int:material_id>')
def delete_material(material_id):

    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM materials WHERE id=%s", (material_id,))
    conn.commit()
    conn.close()

    return redirect(request.referrer)

@app.route('/course/<int:course_id>')
def view_course(course_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Course info
    cursor.execute("SELECT * FROM courses WHERE id=%s", (course_id,))
    course = cursor.fetchone()

    # Materials
    cursor.execute("SELECT * FROM materials WHERE course_id=%s ORDER BY created_at DESC", (course_id,))
    materials = cursor.fetchall()

    # Assignments
    cursor.execute("SELECT * FROM assignments WHERE course_id=%s", (course_id,))
    assignments = cursor.fetchall()

    return render_template('course_detail.html',course=course,materials=materials,assignments=assignments)

from flask import send_from_directory

@app.route('/materials/<filename>')
def serve_material(filename):
    return send_from_directory(app.config['MATERIAL_FOLDER'], filename)

@app.route('/grade_submission_inline', methods=['POST'])
def grade_submission_inline():

    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect('/')

    submission_id = request.form['submission_id']
    marks = request.form['marks']
    feedback = request.form['feedback']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if already graded
    cursor.execute("SELECT * FROM grades WHERE submission_id = %s", (submission_id,))
    existing = cursor.fetchone()

    if existing:
        # Update
        cursor.execute("""
            UPDATE grades
            SET marks = %s, feedback = %s
            WHERE submission_id = %s
        """, (marks, feedback, submission_id))
    else:
        # Insert
        cursor.execute("""
            INSERT INTO grades (submission_id, marks, feedback)
            VALUES (%s, %s, %s)
        """, (submission_id, marks, feedback))

    conn.commit()
    conn.close()

    return redirect(request.referrer)   # stay on same page


if __name__ == "__main__":
    app.run(debug=True)