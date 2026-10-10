# SI-Batch 派员单位参保信息收集系统

Flask + SQLite 单体应用：前台导入增员/减员 `.xls` 表，系统解析入库并生成社保、医保、省工伤报盘文件，按角色（前台 / 社保 / 医保 / 管理员）分配功能权限。所有业务映射、字典、默认值均存放在数据库中，可在管理员后台维护。

- 技术栈：Python 3 + Flask 3.1 + SQLite（无外部数据库服务）
- 监听地址：`0.0.0.0:5000`（局域网内其他电脑可直接访问）
- 数据文件：`si_batch.db`（仓库根目录），上传件在 `uploads/`，报盘在 `outputs/`

## 一、环境要求

- Python 3（本机启用了 PEP 668，**必须使用虚拟环境 `.venv`，不要在系统 Python 上直接 `pip install`**）
- 操作系统：Linux（脚本为 bash；其他系统请手动执行 venv 命令）

## 二、安装

在仓库根目录 `/home/ubuntu/coding/SI-Batch` 下执行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

依赖（`requirements.txt`，勿随意新增）：`Flask==3.1.3`、`openpyxl==3.1.5`、`xlrd==2.0.2`、`xlwt==1.3.0`。

## 三、初始化数据库

```bash
.venv/bin/python -c "import db; db.init_db(); db.seed_data()"
```

- `db.init_db()`：建表与索引，幂等（`CREATE TABLE IF NOT EXISTS`），可重复执行。
- `db.seed_data()`：写入业务字典/映射/默认值，内部先调 `init_db()`，全部 `INSERT OR IGNORE`，**幂等，可重复执行，不会覆盖管理员改过的数据**。
- 种子账号由 `auth.ensure_seed_users()` 在应用启动时自动幂等创建，无需单独执行。

## 四、启动

一键启动（推荐，自动处理 venv、依赖、数据库初始化）：

```bash
./run.sh
```

等价的手动启动：

```bash
.venv/bin/python app.py
```

启动成功后打印 `Listening on 0.0.0.0:5000`。健康检查：浏览器打开 `http://<服务器IP>:5000/healthz`。

停止：前台运行时按 `Ctrl-C`；后台运行时 `kill <PID>`。

## 五、默认账号密码

首次启动自动创建（密码以哈希存储，仅 `auth.py` 中的 `SEED_USERS` 保留明文用于建号）。**上线后请立即修改管理员密码**（`/admin/users`）。

| 用户名 | 密码 | 角色 | 显示名 |
| --- | --- | --- | --- |
| `admin` | `admin123` | 系统管理员 admin | 系统管理员 |
| `front1` | `123456` | 前台业务员 front | 前台业务员 |
| `social1` | `123456` | 社保管理员 social | 社保管理员 |
| `medical1` | `123456` | 医保管理员 medical | 医保管理员 |

登录页：`http://<服务器IP>:5000/login`。

## 六、局域网访问说明

服务监听 `0.0.0.0:5000`，同一局域网内的其他电脑用浏览器访问 `http://<服务器IP>:5000` 即可。

1. **查本机 IP**：

   ```bash
   ip addr        # 查看网卡 IP（如 192.168.1.10）
   hostname -I    # 一行输出本机 IP
   ```

2. **防火墙放行 5000 端口**（二选一，按系统防火墙选择）：

   ufw（Ubuntu/Debian）：

   ```bash
   sudo ufw allow 5000/tcp
   sudo ufw reload
   ```

   firewalld（CentOS/RHEL/Fedora）：

   ```bash
   sudo firewall-cmd --permanent --add-port=5000/tcp
   sudo firewall-cmd --reload
   ```

3. **其他电脑访问**：浏览器打开 `http://<服务器IP>:5000`（例：`http://192.168.1.10:5000`），用上面的默认账号登录。

4. 若仍无法访问：确认服务器与本机在同一网段、云服务器还需在安全组/安全组规则中放行 5000 端口。

## 七、功能与权限矩阵

访问控制由 `auth.py` 的 `login_required` / `require_role(...)` 装饰器实现；未登录一律跳转 `/login`，越权返回 403。

| 页面 / 路由 | 功能 | front | social | medical | admin |
| --- | --- | :-: | :-: | :-: | :-: |
| `/login` `/logout` | 登录 / 退出 | ✓ | ✓ | ✓ | ✓ |
| `/`（首页） | 按角色展示的统计仪表盘 | ✓ | ✓ | ✓ | ✓ |
| `/healthz` | 健康检查（公开） | ✓ | ✓ | ✓ | ✓ |
| `/upload` | 上传增员/减员 `.xls`，解析入库并展示成功/失败明细 | ✓ | — | — | ✓ |
| `/social` | 社保增员/减员批次列表、生成社保报盘、下载报盘 | — | ✓ | — | ✓ |
| `/medical` | 医保增员/减员批次列表、生成医保报盘、下载报盘 | — | — | ✓ | ✓ |
| `/province_injury` | 省工伤人员信息表维护（增删改、导入、生成报盘） | — | ✓ | — | ✓ |
| `/admin/users` | 用户管理（新增/改密/删除） | — | — | — | ✓ |
| `/admin/units` | 社保/医保单位信息配置 | — | — | — | ✓ |
| `/admin/mappings` | 减员原因映射、通用字典、系统默认值维护 | — | — | — | ✓ |

说明：每个角色的首页只显示与本角色相关的计数与快捷入口（见 `app.py` 的 `index`）；管理员拥有全部业务页面权限，便于排查与代操作。

## 八、目录结构

```
SI-Batch/
├── app.py               # Flask 入口：create_app()、自动注册 web/ 蓝图、python app.py 启动
├── config.py            # 基础设施配置：DATABASE/HOST/PORT/SECRET_KEY/UPLOAD_DIR/OUTPUT_DIR
├── db.py                # SQLite schema + 数据访问层 + init_db()/seed_data()（均幂等）
├── auth.py              # 登录/登出、角色装饰器、种子账号（SEED_USERS）
├── columns.py           # 模板列定义
├── mapping.py           # 输入值 -> 报盘字典值的映射辅助
├── requirements.txt     # Python 依赖（Flask/openpyxl/xlrd/xlwt）
├── run.sh               # 一键启动脚本（venv/依赖/数据库/启动）
├── si_batch.db          # SQLite 数据库（.gitignore 忽略，首次启动自动生成）
├── parser/              # 增员/减员 .xls 解析器
├── generator/           # 社保/医保/省工伤报盘生成器
├── web/                 # 各角色页面蓝图（按 web/<name>.py 自动发现注册）
│   ├── front.py             # /upload 前台上传
│   ├── social.py            # /social 社保
│   ├── medical.py           # /medical 医保
│   ├── province_injury.py   # /province_injury 省工伤
│   ├── admin_users.py       # /admin/users
│   ├── admin_unit.py        # /admin/units
│   └── admin_mapping.py     # /admin/mappings
├── templates/           # Jinja2 模板（login/dashboard/各业务页）
├── static/              # 静态资源
├── uploads/             # 上传的原始 .xls（.gitignore 忽略）
├── outputs/             # 生成的报盘文件（.gitignore 忽略）
└── 输入输出/            # 原始模板与示例数据（业务参考）
```

## 九、常见问题

- **`pip install` 报 externally-managed-environment**：本机启用了 PEP 668，必须使用 `.venv` 虚拟环境，不要绕过。
- **端口被占用**：`ss -ltnp | grep 5000` 查看占用进程，换进程或修改 `config.py` 的 `PORT`。
- **Session 失效/重启后掉登录**：`SECRET_KEY` 未设置时每次重启随机生成。需要固定时设置环境变量：

  ```bash
  SI_BATCH_SECRET_KEY="<随机长字符串>" ./run.sh
  ```

- **数据库损坏**：删除 `si_batch.db` 后重新执行第三节的初始化命令（或直接删库后再跑 `./run.sh`，会自动重建）。
