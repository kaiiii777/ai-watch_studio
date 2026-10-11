# Watch Studio

只保留“卖点分析 + 商品生图”的独立网页应用。

## 启动

图片会先保存到本应用服务器的 `data/uploads/`，调用上游 API 时由服务端读取并转换，不需要额外配置公网图片地址。

如果你希望同时把图片镜像到另一台服务器，再配置以下可选参数：

```bash
export IMAGE_PUBLIC_UPLOAD_BASE="https://你的域名/watch-studio-inputs"
export IMAGE_REMOTE_UPLOAD_HOST="你的图片服务器"
export IMAGE_REMOTE_UPLOAD_USER="ubuntu"
export IMAGE_REMOTE_UPLOAD_DIR="/path/to/public/watch-studio-inputs"
# 如需指定 SSH key：
# export IMAGE_REMOTE_UPLOAD_KEY="/absolute/path/to/key"
python3 server.py
```

然后打开 <http://127.0.0.1:8900>，在页面中保存 HFSY API Key。也可以通过 `IMAGE_APP_PORT` 自定义新应用端口。

`data/` 为服务器端数据目录：API Key、上传图片和最近任务记录都会保存在这里。不要把该目录提交到代码仓库。

生成图片会按访问 IP 和每次任务时间分目录保存：

```text
data/outputs/<访问IP>/<YYYYMMDD-HHMMSS-任务ID>/01.png ... 06.png
```

服务使用多线程 HTTP 服务，支持多人同时使用；实际并发上限取决于上游 API 的并发限制、网络和本机磁盘性能。
