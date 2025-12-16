import base64
import hashlib
import os
import secrets
from datetime import datetime
from io import BytesIO

import psutil
import requests
import urllib3
from database import Database
from flask import Flask, jsonify, render_template, request, send_from_directory
from PIL import Image

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB max upload

# 从环境变量读取AUTH_KEY
AUTH_KEY = os.environ.get("AUTH_KEY", "12345")
db = Database()


def generate_token():
    """生成访问token"""
    return secrets.token_urlsafe(32)


def verify_token(token):
    """验证token"""
    stored_token = db.get_setting("access_token")
    return stored_token and stored_token == token


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/auth", methods=["POST"])
def authenticate():
    """验证AUTH_KEY并生成token"""
    data = request.json
    auth_key = data.get("auth_key", "")

    if auth_key == AUTH_KEY:
        token = generate_token()
        db.set_setting("access_token", token)
        return jsonify({"success": True, "token": token})
    return jsonify({"success": False, "message": "认证失败"}), 401


@app.route("/api/verify", methods=["POST"])
def verify():
    """验证token"""
    data = request.json
    token = data.get("token", "")

    if verify_token(token):
        return jsonify({"success": True})
    return jsonify({"success": False}), 401


@app.route("/api/system-info", methods=["GET"])
def get_system_info():
    """获取系统信息"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # CPU信息
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        # 内存信息
        memory = psutil.virtual_memory()

        # 磁盘信息
        disk = psutil.disk_usage("/")

        return jsonify(
            {
                "cpu": {"percent": cpu_percent, "count": cpu_count},
                "memory": {
                    "total": memory.total,
                    "used": memory.used,
                    "percent": memory.percent,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "percent": disk.percent,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/groups", methods=["GET"])
def get_groups():
    """获取所有分组"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    groups = db.get_all_groups()
    return jsonify(groups)


@app.route("/api/groups", methods=["POST"])
def create_group():
    """创建分组"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    group_id = db.create_group(
        name=data["name"],
        order=data.get("order", 999),
        is_nas_service=data.get("is_nas_service", False),
    )
    return jsonify({"success": True, "group_id": group_id})


@app.route("/api/groups/<int:group_id>", methods=["PUT"])
def update_group(group_id):
    """更新分组"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    db.update_group(group_id, data["name"], data.get("order"))
    return jsonify({"success": True})


@app.route("/api/groups/<int:group_id>", methods=["DELETE"])
def delete_group(group_id):
    """删除分组"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    db.delete_group(group_id)
    return jsonify({"success": True})


@app.route("/api/services", methods=["POST"])
def create_service():
    """创建服务"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    service_id = db.create_service(
        group_id=data["group_id"],
        name=data["name"],
        url_public=data.get("url_public", ""),
        url_local=data.get("url_local", ""),
        icon=data.get("icon", ""),
        order=data.get("order", 999),
    )
    return jsonify({"success": True, "service_id": service_id})


@app.route("/api/services/<int:service_id>", methods=["PUT"])
def update_service(service_id):
    """更新服务"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    db.update_service(
        service_id=service_id,
        name=data["name"],
        url_public=data.get("url_public"),
        url_local=data.get("url_local"),
        icon=data.get("icon"),
        order=data.get("order"),
    )
    return jsonify({"success": True})


@app.route("/api/services/<int:service_id>", methods=["DELETE"])
def delete_service(service_id):
    """删除服务"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    db.delete_service(service_id)
    return jsonify({"success": True})


@app.route("/api/fetch-icon", methods=["POST"])
def fetch_icon():
    """获取网站图标"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    url = data.get("url", "")

    try:
        # 禁用SSL警告
        import warnings

        warnings.filterwarnings("ignore", message="Unverified HTTPS request")

        from urllib.parse import urlparse

        parsed = urlparse(url)
        print(parsed)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        favicon_urls = [
            f"{base_url}/favicon.ico",
            f"{base_url}/favicon.png",
            f"{base_url}/apple-touch-icon.png",
            f"{base_url}/apple-touch-icon-precomposed.png",
            f"{base_url}/static/favicon.ico",
            f"{url}/favicon.ico",
        ]
        print(favicon_urls)
        for favicon_url in favicon_urls:
            try:
                # 添加 verify=False 跳过TLS验证
                response = requests.get(favicon_url, timeout=5, verify=False)
                if response.status_code == 200:
                    # 转换为base64
                    icon_base64 = base64.b64encode(response.content).decode("utf-8")
                    content_type = response.headers.get("content-type", "image/x-icon")
                    return jsonify(
                        {
                            "success": True,
                            "icon": f"data:{content_type};base64,{icon_base64}",
                        }
                    )
            except Exception as e:
                print(f"尝试获取图标失败 {favicon_url}: {e}")
                continue

        return jsonify({"success": False, "message": "无法获取图标"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/upload-icon", methods=["POST"])
def upload_icon():
    """上传自定义图标"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.json
        image_data = data.get("image", "")

        # 解析base64图片
        if "," in image_data:
            image_data = image_data.split(",")[1]

        img_bytes = base64.b64decode(image_data)
        img = Image.open(BytesIO(img_bytes))

        # 调整大小到128x128
        img.thumbnail((128, 128), Image.Resampling.LANCZOS)

        # 转换回base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return jsonify({"success": True, "icon": f"data:image/png;base64,{img_base64}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/settings", methods=["GET"])
def get_settings():
    """获取设置"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    force_network = db.get_setting("force_network_mode")
    return jsonify({"force_network_mode": force_network or "auto"})


@app.route("/api/settings", methods=["POST"])
def save_settings():
    """保存设置"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_token(token):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    if "force_network_mode" in data:
        db.set_setting("force_network_mode", data["force_network_mode"])

    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
