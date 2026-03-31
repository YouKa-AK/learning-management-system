from flask import Blueprint, render_template, request, redirect, url_for

auth_bp = Blueprint('auth', __name__)

# 👉 Root URL redirects to login
@auth_bp.route('/')
def home():
    return redirect(url_for('auth.login'))

@auth_bp.route('/root')
def root_test():
    return "ROOT ROUTE WORKING"




@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    message = ""
    status = ""

    if request.method == 'POST':
        # later you can add DB logic here
        pass

    return render_template('login.html', message=message, status=status)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('register.html')
