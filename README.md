# 选股策略跟踪工具 后端

## 项目说明

这是一个基于 FastAPI 的选股策略跟踪工具后端实现，包含策略、批次、个股、行情同步、收益指标和权限控制。

## 运行要求

- Python 3.11+
- 推荐使用虚拟环境

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 1145
```

## 数据库

默认使用 SQLite 数据库 `./stock_strategy.db`。

可通过环境变量调整运行配置：

- `DATABASE_URL`：数据库连接，默认 `sqlite:///./stock_strategy.db`
- `SECRET_KEY`：JWT 签名密钥，生产环境必须设置
- `CONFIG_FILE`：业务配置文件路径，默认 `config.yaml`
- `CORS_ALLOW_ORIGINS`：允许的前端域名，多个用英文逗号分隔
- `BOOTSTRAP_FIRST_USER_AS_ADMIN`：首个注册用户是否自动成为管理员，默认 `true`

启动时会自动创建基础表，并对 SQLite 补充新增列与索引。生产环境仍建议接入 Alembic 迁移。

## 行情数据源

行情源在 `config.yaml` 中配置：

```yaml
market_data:
  provider: demo  # demo / akshare / tushare / jqdata
  tushare:
    token: ""
  jqdata:
    username: ""
    password: ""
```

也可以用环境变量覆盖敏感信息：

- `MARKET_DATA_PROVIDER`
- `TUSHARE_TOKEN`
- `JQDATA_USERNAME`
- `JQDATA_PASSWORD`

第三方行情包按需安装即可：

```bash
pip install akshare
pip install tushare
pip install jqdatasdk
```

`akshare` 不需要 token；`tushare` 需要 token；`jqdata` 对应聚宽 `jqdatasdk` 账号。常见指数别名如 `CSI300`、`SZ50` 已在 `config.yaml` 中配置，可继续扩展。

## API 路径

- `/api/auth/login`
- `/api/auth/register`
- `/api/auth/me`
- `/api/users`
- `/api/strategies`
- `/api/strategies/{strategyId}/batches`
- `/api/batches/{batchId}/stocks`
- `/api/batches/{batchId}/stocks/bulk`
- `/api/data/sync`
- `/api/data/status`
- `/api/data/history`
- `/api/strategies/{strategyId}/metrics`
- `/api/batches/{batchId}/metrics`
- `/api/stocks/{stockCode}/metrics`
- `/api/metrics/hold-return`
- `/api/strategies/{strategyId}/compare-batches`

## 当前实现说明

- 普通注册不会再开放指定角色；首个用户默认作为管理员，后续用户由管理员通过 `/api/users` 创建或调整角色。
- `/api/data/sync` 目前仅允许管理员调用。未配置真实行情服务时，内置 demo 行情生成器用于开发与测试。
- 行情同步后会重算个股、批次、策略三层收益指标，支持累计收益、每日收益、最大涨幅、最大回撤、N/K 持有期收益和批次对比。

## 测试

```bash
.venv/bin/python -m pytest
```

## 前端

前端位于 `frontend/`，使用 React + Vite：

```bash
cd frontend
npm install
npm run dev -- --port 19198
```

默认通过 Vite 代理访问 `http://127.0.0.1:19198/api`。生产或跨域部署时可设置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:19198 npm run dev
```

生产构建：

```bash
cd frontend
npm run build
```

## Docker 一键部署

前后端可以打包到同一个容器：FastAPI 提供 `/api`，同时托管 React 构建后的页面。

```bash
docker compose up --build -d
```

访问：

- 前端页面：`http://127.0.0.1:19198/`
- API 文档：`http://127.0.0.1:11451/docs`

停止：

```bash
docker compose down
```

SQLite 数据保存在 Docker volume `stock_strategy_data` 中。`config.yaml` 会以只读方式挂载到容器内，可以直接修改它切换 `demo / akshare / tushare / jqdata` 数据源，然后重启：

```bash
docker compose restart
```

生产环境建议至少设置：

```bash
export SECRET_KEY="replace-with-a-long-random-secret"
export MARKET_DATA_PROVIDER="demo"
export TUSHARE_TOKEN=""
export JQDATA_USERNAME=""
export JQDATA_PASSWORD=""
docker compose up --build -d
```

如果选择 `akshare`、`tushare` 或 `jqdata`，可以通过构建参数一次性安装对应第三方包：

```bash
MARKET_EXTRAS="akshare tushare jqdatasdk" docker compose up --build -d
```
