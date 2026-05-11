import csv
import json
import os
from functools import wraps
from pathlib import Path

import cv2
import numpy as np
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from annotations.models import Annotation, UploadedImage

from mammo_paths import COORDINATES, LABEL_CSV, MASKS, POLYGONS, ensure_data_dirs

from .cv_utils import cv2_imread, cv2_imwrite

_ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _label_csv_path() -> Path:
    ensure_data_dirs()
    return LABEL_CSV


def _ensure_label_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["image", "polygon", "point", "x", "y"])


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            return jsonify({"error": "Unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapped


def _current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.objects.filter(id=uid).first()


def create_app() -> Flask:
    pkg = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        static_folder=str(pkg / "static"),
        template_folder=str(pkg / "templates"),
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-mammoai-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("annotate"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            user = authenticate(username=username, password=password)
            if user is None:
                return render_template(
                    "login.html", error="Invalid username or password."
                ), 400
            session["user_id"] = user.id
            session["username"] = user.username
            nxt = request.args.get("next") or url_for("annotate")
            return redirect(nxt)
        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""
            if not username or not email or not password:
                return render_template(
                    "register.html", error="All fields are required."
                ), 400
            if User.objects.filter(username=username).exists():
                return render_template(
                    "register.html", error="That username is already taken."
                ), 400
            user = User.objects.create_user(
                username=username, email=email, password=password
            )
            user.save()
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("annotate"))
        return render_template("register.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/annotate")
    @login_required
    def annotate():
        return render_template(
            "annotate.html",
            username=session.get("username", ""),
        )

    @app.route("/api/images", methods=["GET"])
    @api_login_required
    def api_list_images():
        user = _current_user()
        rows = []
        for img in UploadedImage.objects.filter(user=user).order_by("-uploaded_at")[:100]:
            rows.append(
                {
                    "id": img.id,
                    "original_name": img.original_name,
                    "url": url_for("serve_uploaded_image", image_id=img.id),
                }
            )
        return jsonify({"images": rows})

    @app.route("/api/image/<int:image_id>/file", methods=["GET"])
    @api_login_required
    def serve_uploaded_image(image_id):
        user = _current_user()
        try:
            img = UploadedImage.objects.get(id=image_id, user=user)
        except UploadedImage.DoesNotExist:
            return jsonify({"error": "Not found"}), 404
        path = Path(img.file.path)
        if not path.is_file():
            return jsonify({"error": "File missing on disk"}), 404
        return send_file(path, as_attachment=False)

    @app.route("/api/image/<int:image_id>/annotations", methods=["GET"])
    @api_login_required
    def api_image_annotations(image_id):
        user = _current_user()
        try:
            img_row = UploadedImage.objects.get(id=image_id, user=user)
        except UploadedImage.DoesNotExist:
            return jsonify({"error": "Not found"}), 404
        polygons = []
        for ann in Annotation.objects.filter(image=img_row).order_by("polygon_index"):
            try:
                polygons.append(json.loads(ann.points_json))
            except json.JSONDecodeError:
                continue
        return jsonify({"polygons": polygons})

    @app.route("/api/upload", methods=["POST"])
    @api_login_required
    def api_upload():
        user = _current_user()
        if "file" not in request.files:
            return jsonify({"error": "No file field"}), 400
        f = request.files["file"]
        if not f or not f.filename:
            return jsonify({"error": "Empty filename"}), 400
        raw = f.filename
        ext = Path(raw).suffix.lower()
        if ext not in _ALLOWED_IMAGE_EXT:
            return jsonify({"error": "Unsupported image type"}), 400
        safe = secure_filename(raw) or f"upload{ext}"
        obj = UploadedImage(user=user, original_name=raw)
        obj.file.save(safe, ContentFile(f.read()), save=True)
        return jsonify(
            {
                "id": obj.id,
                "original_name": obj.original_name,
                "url": url_for("serve_uploaded_image", image_id=obj.id),
            }
        )

    @app.route("/api/annotation", methods=["POST"])
    @api_login_required
    def api_save_annotation():
        user = _current_user()
        data = request.get_json(silent=True) or {}
        image_id = data.get("image_id")
        points = data.get("points")
        if image_id is None or not isinstance(points, list):
            return jsonify({"error": "image_id and points[] required"}), 400
        if len(points) < 3:
            return jsonify({"error": "Minimum 3 points required"}), 400
        try:
            img_row = UploadedImage.objects.get(id=int(image_id), user=user)
        except (UploadedImage.DoesNotExist, ValueError):
            return jsonify({"error": "Image not found"}), 404

        try:
            pts = [[float(p[0]), float(p[1])] for p in points]
        except (TypeError, IndexError, ValueError):
            return jsonify({"error": "Invalid point format"}), 400

        disk_path = os.path.normpath(img_row.file.path)
        image_bgr = cv2_imread(disk_path)
        if image_bgr is None:
            return jsonify({"error": "Could not read image from disk"}), 500

        ensure_data_dirs()
        poly_id = Annotation.objects.filter(image=img_row).count()
        base = Path(img_row.original_name).stem
        stem = f"{base}_{img_row.id}_poly{poly_id}"

        mask_rel = os.path.join("data", "masks", f"{stem}.png")
        viz_rel = os.path.join("data", "polygons", f"{base}_{img_row.id}_viz{poly_id}.png")
        json_rel = os.path.join("data", "coordinates", f"{stem}.json")

        mask_abs = MASKS / f"{stem}.png"
        viz_abs = POLYGONS / f"{base}_{img_row.id}_viz{poly_id}.png"
        json_abs = COORDINATES / f"{stem}.json"

        arr = np.array(pts, dtype=np.int32)
        mask = np.zeros(image_bgr.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [arr], 255)
        if not cv2_imwrite(str(mask_abs), mask, ".png"):
            return jsonify({"error": "Failed to write mask"}), 500

        viz = image_bgr.copy()
        cv2.polylines(viz, [arr], True, (0, 255, 255), 2)
        for x, y in pts:
            cv2.circle(viz, (int(x), int(y)), 5, (0, 0, 255), -1)
        if not cv2_imwrite(str(viz_abs), viz, ".png"):
            return jsonify({"error": "Failed to write visualization"}), 500

        json_abs.write_text(json.dumps(pts, indent=2), encoding="utf-8")

        Annotation.objects.create(
            image=img_row,
            polygon_index=poly_id,
            points_json=json.dumps(pts),
            mask_relative=mask_rel.replace("\\", "/"),
            viz_relative=viz_rel.replace("\\", "/"),
            coords_relative=json_rel.replace("\\", "/"),
        )

        label_path = _label_csv_path()
        _ensure_label_csv_header(label_path)
        with label_path.open("a", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            for i, (x, y) in enumerate(pts):
                w.writerow([img_row.original_name, poly_id, i + 1, int(x), int(y)])

        return jsonify(
            {
                "ok": True,
                "polygon_index": poly_id,
                "mask": mask_rel.replace("\\", "/"),
                "visualization": viz_rel.replace("\\", "/"),
                "coordinates_json": json_rel.replace("\\", "/"),
            }
        )

    return app
