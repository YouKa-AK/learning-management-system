from flask import Blueprint, request, jsonify
from app import db
from app.models.course import Course

course_bp = Blueprint("course_bp", __name__)

@course_bp.route("/courses", methods=["POST"])
def create_course():
    data = request.json
    course = Course(
        title=data["title"],
        teacher_id=data["teacher_id"]
    )
    db.session.add(course)
    db.session.commit()
    return jsonify({"message": "Course created successfully"})
