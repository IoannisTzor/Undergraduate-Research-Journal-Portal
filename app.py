from flask import Flask, render_template

from flask import Flask, render_template, session, redirect, url_for, request, abort

from functools import wraps

app = Flask(__name__)
app.secret_key = "dev-only-change-later"

ROLES = ["guest", "submitter", "reviewer", "editor", "admin"]

def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/past_issues")
def past_issues():
    return render_template("past_issues.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")

@app.route("/dev/role/<role>")
def switch_role(role):
    if role in ROLES:
        session["role"] = role
    return redirect(request.referrer or url_for("home"))


@app.context_processor
def inject_role():
    return {
        "current_role": session.get("role", "guest"),
        "roles": ROLES,
    }

@app.route("/submit")
@role_required("submitter")
def submit_study():
    return render_template("submit_study.html")

@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403