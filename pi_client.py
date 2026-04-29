"""
pi_client.py - Pi 文件服务器客户端
支持上传简报到 Pi、从 Pi 下载简报列表
"""
import requests
import json
import os


class PiClient:
    def __init__(self, ip: str, port: int = 5000):
        self.base_url = f"http://{ip}:{port}"

    def list_reports(self) -> list[str]:
        """获取 Pi 上的简报列表"""
        resp = requests.get(f"{self.base_url}/list", timeout=10)
        resp.raise_for_status()
        return json.loads(resp.text)

    def upload_report(self, filepath: str) -> bool:
        """上传本地简报到 Pi（原始 body + Filename header）"""
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            data = f.read()
        resp = requests.post(
            f"{self.base_url}/upload",
            data=data,
            headers={"Filename": filename, "Content-Type": "application/octet-stream"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.text == "OK"

    def download_report(self, filename: str, save_dir: str) -> str:
        """从 Pi 下载指定简报到本地目录"""
        save_path = os.path.join(save_dir, filename)
        resp = requests.get(f"{self.base_url}/download/{filename}", timeout=60)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path
