from flask import Flask, render_template

from flask import Flask, render_template, session, redirect, url_for, request

app = Flask(__name__)
app.secret_key = "dev-only-change-later"

ROLES = ["guest", "submitter", "reviewer", "editor", "admin"]


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