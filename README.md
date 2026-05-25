# SmartStock - 智能炒股分析系统

个人量化研究工具，覆盖数据→识别→回测→监控全链路。

## 快速开始

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
python scripts/fetch_data.py    # 拉取沪深300日线数据
python -m uvicorn backend.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`

## 技术栈

- 后端：Python FastAPI + PyTorch + pandas + akshare
- 前端：Vite + React 18 + TypeScript + lightweight-charts
- 存储：SQLite
