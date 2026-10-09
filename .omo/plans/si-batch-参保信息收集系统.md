# 派遣员工参保信息收集系统

## TL;DR

> **Quick Summary**: 构建一个局域网可访问的 Flask 单体 Web 系统：前台业务员导入增员/减员表（.xls），后台社保管理员与医保管理员各自独立生成并下载对应报盘（社保失业工伤 / 省工伤 / 省医保 / 市医保），带简单的分权分账号，所有业务规则（映射、单位信息、字典、默认值）均存数据库可配置、不硬编码。
>
> **Deliverables**:
> - 登录/分权系统（前台业务员 / 社保管理员 / 医保管理员 / admin 四角色）
> - 增员表、减员表导入解析入库
> - 7 种报盘生成+下载：社保增员、社保减员、省工伤减员、省医保增员、市医保增员、省医保减员、市医保减员
> - 省工伤人员信息表（独立维护：导入/查看/编辑/删除）
> - 后台配置页（用户、单位信息、减员原因映射、字典映射、默认值）
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: T1 骨架 → T2 数据库 → T4 列定义/种子 → T6/T8 解析/生成 → T20 集成 → F1-F4 审查

---

## Context

### Original Request
派遣员工参保信息收集系统：前台业务员导入参保信息表（增员）或减员表，后台分别生成社保失业工伤的报盘和医保的报盘；社保失业工伤和医保由不同业务人员管理；做简单分权分账号功能。目标：最快用上。模板在 `输入输出/` 目录。

### Interview Summary

**关键决策**：
- 部署：局域网多机访问（后台一台机器当服务器，其他人浏览器访问该机 IP）
- 技术栈：Python + Flask + SQLite + Jinja2 单体（服务端渲染，无前端构建）
- 测试：仅 Agent 执行验证（无自动化单测）
- 数据库：SQLite（量级小、零运维、完全够用，不换 MySQL/PostgreSQL）
- 硬性约束「不硬编码」：减员原因映射、单位信息、字典映射、默认值全部存 DB + 后台可配置
- 申报工资 = 合同工资（社保和医保都取此字段）
- 省/市医保按「医保参保属地」区分；医保报盘分省、市两个独立文件；医保由一人管理
- 省工伤：只做减员报盘（用单位职工停保模板格式），名单单独维护（按增员模板字段设计、保留冗余字段），归社保管理员管

**日期规则（关键业务逻辑）**：
- 社保 参保日期 = 合同开始时间
- 社保 停保日期 = 合同终止日期
- 省医保 本次参保时间 = 合同开始时间
- 市医保 本次参保时间 = 医保参保年月 + 01（如 `202006` → `20200601`）
- 社保减员报盘末尾追加「合同终止原因」列（原 5 列 + 追加 1 列，方便核对）
- 医保减员保持 3 列（姓名/证件类型/证件号码），不追加

**研究结论（模板已全部读取）**：
- 输入增员表 60 列（.xls，xlrd 读），输入减员表 16 列（.xls）
- 社保增员 .xlsx 27 列（含合并单元格 + 示例行「小明」须保留，数据从第 5 行开始）
- 社保减员 .xlsx 5 列，停保原因 9 个固定值（Sheet2 字典）
- 医保增员 .xls 17 列（日期为 Excel 序列号，非文本）
- 医保减员 .xls 3 列
- 性别/出生日期从身份证号推导（第 17 位奇偶、第 7-14 位）
- 字段值普遍带「代码-」前缀（如 `01-汉族`），需剥离或映射

### Metis Review
**已识别的关键风险（已全部在方案中规避）**：
- 社保增员 27 列 vs 早期误记 23 列 → 已补全（实际工作单位编号/名称/统一社会信用代码/外国人永久居留中文名称）
- 社保增员合并单元格 + 示例行必须保留 → 生成器须复制模板结构
- 数字精度风险（16 位工资账号、身份证 X 后缀、手机号/邮编前导零、医保日期序列号）→ 全部按文本/正确类型处理
- xlwt 未装且系统 Python 受 PEP 668 保护 → 用 venv 安装依赖
- 字段映射「前缀剥离 vs 字典查找」须区分 → 建立字典映射表（前缀剥离 + 字典查找两类）

---

## Work Objectives

### Core Objective
前台导入增员/减员表 → 入库 → 社保管理员生成社保/省工伤报盘、医保管理员生成省/市医保报盘 → 下载，全程分角色控制，业务规则全部可配置。

### Concrete Deliverables
- `app.py` + `config.py` + `requirements.txt` + `db.py` + `auth.py`
- `parser/`：`enroll_parser.py`、`reduce_parser.py`
- `generator/`：`social_enroll.py`、`social_reduce.py`、`province_injury_reduce.py`、`medical_enroll.py`、`medical_reduce.py`
- `mapping.py`：身份证推导、日期转换、前缀剥离工具
- `templates/`：login/base/dashboard/upload/social/province_injury/medical/admin_users/admin_units/admin_mappings
- `static/`：css/js（Bootstrap）
- 数据库 `si_batch.db`（SQLite）+ 全部种子数据
- 启动脚本 + 部署说明

### Definition of Done
- [ ] `source .venv/bin/activate && python app.py` 启动，监听 `0.0.0.0:5000`，局域网可访问
- [ ] 用真实模板导入增员表（张三样本）→ 生成社保增员报盘，字段值/格式与模板一致
- [ ] 用真实模板导入减员表 → 生成社保减员（含合同终止原因列）、省/市医保减员
- [ ] 省工伤信息表可导入/查看/编辑/删除，可生成省工伤减员报盘
- [ ] 前台/社保/医保/admin 四角色权限隔离正确
- [ ] 所有映射/单位信息/默认值可在后台配置页修改并生效

### Must Have
- 4 角色登录分权（前台/社保/医保/admin），密码哈希存储
- 增员/减员导入解析（.xls），必录项校验
- 7 种报盘按各自精确模板结构生成（含社保增员合并单元格+示例行、医保日期序列号）
- 社保减员报盘末尾追加合同终止原因列
- 省/市医保按属地拆分独立文件
- 省工伤人员信息表独立 CRUD + 导入
- 减员原因映射、单位信息、字典、默认值全部 DB 可配置

### Must NOT Have (Guardrails)
- 不硬编码任何业务规则/映射/字典/默认值（全部走 DB）
- 不做公积金（后续升级）、意外险报盘、生育保险、历史补录/补缴、省工伤增员
- 不引入 MySQL/PostgreSQL 等外部数据库服务
- 不引入前端构建工具链（无 npm/webpack）
- 不做自动化单元测试（仅 Agent 执行验证）
- 不生成"通用 Excel 模板类"（4 种输出文件结构不同，须各自专用生成器）
- 不擅自删除社保增员模板的示例行或合并单元格

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — 所有验证由执行代理完成。

### Test Decision
- **Infrastructure exists**: NO（本项目无测试框架）
- **Automated tests**: None（仅 Agent 执行验证）
- **Framework**: 无单测；验证用 Bash/Python 脚本 + curl + Playwright（UI 部分）
- **Agent-Executed QA**: 每个任务强制

### QA Policy
每个任务包含 Agent 可执行 QA 场景，证据保存到 `.omo/evidence/task-{N}-{slug}.{ext}`。

- **解析/生成器**：Bash(Python) — 导入模块、用真实模板文件跑通、断言输出文件存在 + 用 openpyxl/xlrd 读回断言单元格值
- **路由/页面**：Bash(curl) — 启动服务、断言 HTTP 状态与响应内容
- **登录/分权**：curl 带 session cookie 断言越权被拒；Playwright 断言页面渲染
- **数字精度**：断言 16 位工资账号、X 后缀身份证导入导出不变

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (基础，5 任务，最大并行):
├── T1  项目骨架 + venv + 依赖 + Flask 入口 + config.py  [quick]
├── T2  数据库 schema（SQLite 全部建表）                 [quick]
├── T3  认证模块（登录/登出/session/角色装饰器 + 种子admin）[unspecified-high]
├── T4  模板常量/列定义 + 字典/映射/默认值种子数据        [unspecified-high]
└── T5  工具函数（身份证推导/日期转换/前缀剥离）          [deep]

Wave 2 (核心逻辑，7 任务，最大并行):
├── T6  增员表解析器（60列 .xls → 结构化记录 + 校验 + 入库）[deep]
├── T7  减员表解析器（16列 .xls → 结构化记录 + 入库）      [unspecified-high]
├── T8  社保增员生成器（.xlsx 27列 复制模板结构）          [deep]
├── T9  社保减员生成器（.xlsx 5列 + 追加合同终止原因）     [unspecified-high]
├── T10 省工伤减员生成器（.xlsx 停保5列）                 [unspecified-high]
├── T11 医保增员生成器（.xls 17列 省/市拆分 日期序列号）   [deep]
└── T12 医保减员生成器（.xls 3列 省/市拆分）              [quick]

Wave 3 (UI 页面 + 路由，7 任务，最大并行):
├── T13 前台上传页面+路由（增/减员上传 + 批次列表）        [visual-engineering]
├── T14 社保管理员页面+路由（社保增/减报盘生成下载）       [visual-engineering]
├── T15 省工伤管理页面+路由（CRUD+导入+减员报盘生成）      [visual-engineering]
├── T16 医保管理员页面+路由（省/市医保增/减报盘）          [visual-engineering]
├── T17 admin 用户管理页面+路由                           [quick]
├── T18 admin 单位信息配置页面+路由                       [quick]
└── T19 admin 映射/字典/默认值配置页面+路由                [quick]

Wave 4 (集成 + 部署，2 任务):
├── T20 首页仪表盘 + 路由整合 + 权限联调                   [unspecified-high]
└── T21 部署文档 + README + 启动脚本 + 局域网访问说明       [quick]

Wave FINAL (4 并行审查):
├── F1 计划合规审计 (oracle)
├── F2 代码质量审查 (unspecified-high)
├── F3 真实手动 QA (unspecified-high)
└── F4 范围保真检查 (deep)
-> 汇总结果 -> 等待用户明确「okay」

Critical Path: T1 → T2 → T4 → T6/T8 → T20 → F1-F4 → 用户确认
Max Concurrent: 7（Wave 2 与 Wave 3）
```

### Dependency Matrix

- **1**：无 → 供 2-21 使用
- **2**：无 → 被 3、4 依赖
- **3**：2 → 被 13-20 依赖
- **4**：2 → 被 6-12 依赖
- **5**：无 → 被 6-12 依赖
- **6**：4、5 → 被 13、14、16 依赖
- **7**：4、5 → 被 13、14、16 依赖
- **8**：4、5 → 被 14 依赖
- **9**：4、5 → 被 14 依赖
- **10**：4、5 → 被 15 依赖
- **11**：4、5 → 被 16 依赖
- **12**：4、5 → 被 16 依赖
- **13**：3、6、7 → 被 20 依赖
- **14**：3、8、9 → 被 20 依赖
- **15**：3、10 → 被 20 依赖
- **16**：3、11、12 → 被 20 依赖
- **17-19**：3 → 被 20 依赖
- **20**：13-19 → 被 21 依赖
- **21**：20 → 无

### Agent Dispatch Summary

- **Wave 1**：5 — T1→quick、T2→quick、T3→unspecified-high、T4→unspecified-high、T5→deep
- **Wave 2**：7 — T6→deep、T7→unspecified-high、T8→deep、T9→unspecified-high、T10→unspecified-high、T11→deep、T12→quick
- **Wave 3**：7 — T13-T16→visual-engineering、T17-T19→quick
- **Wave 4**：2 — T20→unspecified-high、T21→quick
- **FINAL**：4 — F1→oracle、F2→unspecified-high、F3→unspecified-high、F4→deep

---

## TODOs

---

- [ ] 1. 项目骨架 + venv + 依赖 + Flask 入口 + config.py

  **What to do**:
  - 在 `/home/ubuntu/coding/SI-Batch` 下创建 Python venv（`.venv`），安装依赖：`flask`、`openpyxl`、`xlrd`、`xlwt`，写 `requirements.txt` 固化版本
  - 建目录结构：`parser/`、`generator/`、`templates/`、`static/`、`uploads/`、`outputs/`
  - 写 `config.py`：数据库路径、上传/输出目录、监听 host/port、SECRET_KEY、上传允许扩展名
  - 写 `app.py`：Flask 应用入口，加载 config，注册蓝图占位，启动即监听 `0.0.0.0:5000`
  - `git init` + 首次提交，`.gitignore` 排除 `.venv/`、`uploads/`、`outputs/`、`*.db`

  **Must NOT do**:
  - 不装 MySQL/PostgreSQL 客户端；不引入 npm/webpack 前端构建
  - 不在 config.py 里写业务映射/字典/默认值（那些走 DB，属于 T4）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯脚手架，无业务逻辑
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 T2、T5 并行）
  - **Blocks**: T3、T4、T6-T21
  - **Blocked By**: None

  **References**:
  - 无现有代码（全新项目）。目录仅含 `输入输出/` 模板文件夹。

  **Acceptance Criteria**:
  - [ ] `source .venv/bin/activate && python app.py` 启动成功，打印 `Listening on 0.0.0.0:5000`
  - [ ] `pip list` 显示 flask/openpyxl/xlrd/xlwt 已装
  - [ ] `git status` 干净（.venv、uploads、outputs、*.db 被 ignore）

  **QA Scenarios**:
  ```
  Scenario: 应用可启动
    Tool: Bash
    Steps:
      1. cd /home/ubuntu/coding/SI-Batch && source .venv/bin/activate
      2. python -c "from app import app; print(app.name)"
    Expected Result: 打印 app 名称，无 import 错误
    Failure Indicators: ImportError / ModuleNotFoundError
    Evidence: .omo/evidence/task-1-startup.txt

  Scenario: venv 依赖齐全
    Tool: Bash
    Steps:
      1. source .venv/bin/activate && pip list | grep -iE "flask|openpyxl|xlrd|xlwt"
    Expected Result: 4 个包均列出
    Evidence: .omo/evidence/task-1-deps.txt
  ```

  **Commit**: YES
  - Message: `chore(init): project skeleton, venv, deps, flask entry`

- [ ] 2. 数据库 schema（SQLite 全部建表）

  **What to do**:
  - 写 `db.py`，用 sqlite3 建立连接（`sqlite3.Row` 行工厂）+ 建表函数 + 薄数据访问层（增删改查辅助函数）
  - 建以下表（含合理索引）：
    - `users`(id, username UNIQUE, password_hash, role, display_name, created_at)
    - `unit_config`(id, insurance_type ['social'|'medical'], unit_code, unit_name) — 社保/医保单位信息
    - `mapping_stop_reason`(id, source_reason, social_stop_reason, medical_change_reason) — 减员原因映射
    - `dict_mapping`(id, category, source_code, target_value) — 通用字典映射（民族/户口性质/人员身份/证件类型/属地→工作地址）
    - `system_defaults`(id, key, value) — 默认值（婚姻状态/健康状况/编制类型/国籍/农民工标识/临时账户标识/是否兼职工伤/参保身份/模板版本）
    - `import_batches`(id, batch_type ['enroll'|'reduce'], filename, uploaded_by, uploaded_at, total_rows, status)
    - `enroll_records`(id, batch_id, raw_json, name, id_card, ...关键列单独存) — 增员记录
    - `reduce_records`(id, batch_id, raw_json, name, id_card, ...) — 减员记录
    - `province_injury`(id, name, id_card, settlement_unit, contract_start_date, ...冗余字段, 状态) — 省工伤信息表（按增员模板字段设计）
    - `output_batches`(id, batch_id, insurance_type, batch_type, generated_by, generated_at, filename, file_path, status)
  - 首次运行自动建表（`init_db()` 幂等）

  **Must NOT do**:
  - 不在本任务插入业务种子数据（T4 负责）
  - 不硬编码任何映射/字典值到表结构

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准 schema 定义，无复杂逻辑
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 T1、T5 并行）
  - **Blocks**: T3、T4
  - **Blocked By**: None

  **References**:
  - 表字段来源见 `.omo/drafts/si-batch-参保信息收集系统.md` 的「最终角色与职责」「完整输出报盘清单」；省工伤字段按增员模板 60 列设计

  **Acceptance Criteria**:
  - [ ] `python -c "import db; db.init_db()"` 无报错，生成 `si_batch.db`
  - [ ] `sqlite3 si_batch.db ".tables"` 列出全部 10 张表

  **QA Scenarios**:
  ```
  Scenario: 建表成功
    Tool: Bash
    Steps:
      1. rm -f si_batch.db && python -c "import db; db.init_db()"
      2. sqlite3 si_batch.db ".tables"
    Expected Result: 输出 users/unit_config/mapping_stop_reason/dict_mapping/system_defaults/import_batches/enroll_records/reduce_records/province_injury/output_batches
    Failure Indicators: 表缺失或建表报错
    Evidence: .omo/evidence/task-2-tables.txt
  ```

  **Commit**: YES
  - Message: `feat(db): sqlite schema for all tables`

- [ ] 3. 认证模块（登录/登出/session/角色装饰器 + 种子 admin）

  **What to do**:
  - 写 `auth.py`：密码哈希（werkzeug.security）、登录/登出路由、session 管理、角色装饰器（`@require_role('social')` 等）、当前用户上下文
  - 角色常量：`front`(前台业务员)、`social`(社保管理员)、`medical`(医保管理员)、`admin`
  - 种子账号：首次初始化时创建 `admin`（密码 `admin123`，首次登录可提示改密，至少文档说明）；预留前台/社保/医保示例账号
  - 写 `templates/login.html`、`templates/base.html`（导航栏按角色显示菜单）

  **Must NOT do**:
  - 不实现自助注册、不实现密码找回（admin 在后台管账号）
  - 不用明文存密码

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 涉及 session 与权限，需正确性
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 T4、T5 并行）
  - **Blocks**: T13-T20
  - **Blocked By**: T2

  **References**:
  - Flask session 用法、werkzeug.security generate_password_hash/check_password_hash

  **Acceptance Criteria**:
  - [ ] 登录成功后 session 存 role；未登录访问受保护路由被重定向到 /login
  - [ ] 不同角色访问越权路由返回 403

  **QA Scenarios**:
  ```
  Scenario: 登录成功 + 角色会话
    Tool: Bash (curl)
    Steps:
      1. 启动 app（后台）
      2. curl -c /tmp/c.txt -d "username=admin&password=admin123" http://localhost:5000/login
      3. curl -b /tmp/c.txt http://localhost:5000/  (首页)
    Expected Result: 登录跳转成功；首页返回 200 且含当前用户名
    Failure Indicators: 登录失败/首页重定向到 /login
    Evidence: .omo/evidence/task-3-login.txt

  Scenario: 越权被拒
    Tool: Bash (curl)
    Steps:
      1. 用 front 角色账号登录
      2. curl -b /tmp/c.txt http://localhost:5000/admin/users
    Expected Result: 返回 403
    Failure Indicators: 返回 200 或泄露页面
    Evidence: .omo/evidence/task-3-forbidden.txt
  ```

  **Commit**: YES
  - Message: `feat(auth): login/logout/session/role decorators`

- [ ] 4. 模板常量/列定义 + 字典/映射/默认值种子数据

  **What to do**:
  - 在 `config.py`（或独立 `columns.py`）定义输入/输出各模板的列名常量与列索引（精确到列号，含 27 列社保增员、17 列医保增员等）
  - 在 `db.py` 增加 `seed_data()` 函数，预置：
    - `dict_mapping`：民族（01-汉族→汉族）、户口性质（11-本地非农业户口（本地城镇）→非农业户口（城镇）等）、人员身份（91-干部→职员、92-工人→企业职工）、证件类型（空/居民身份证→居民身份证（户口簿））、属地→工作地址（220100000000→长春市市本级 等）
    - `mapping_stop_reason`：合同终止原因 16 码 → 社保停保原因 9 值 的**预置默认映射**（标记「待用户核对」，admin 可改）
    - `system_defaults`：婚姻状态=未说明的婚姻状况、健康状况=健康或良好、编制类型=非在编、国籍=中国、农民工标识=非农民工、临时账户标识=一般账户、是否兼职工伤=否、参保身份=企业职工、模板版本=1.0
    - `unit_config`：社保/医保单位信息留空（admin 后台填）
  - 默认减员原因映射（预置，可改）：
    - 01-在试用期被证明不符合录用条件→用人单位辞退；02-劳动者被依法追究刑事责任→人员被判刑收监执行；03-严重违反用人单位规章制度→用人单位辞退；04-工作调转→工作关系调转；07-劳动合同到期本人提出→个人原因解除；08-劳动合同到期单位提出→用人单位辞退；09-职工个人原因→个人原因解除；10-用人单位裁员→用人单位辞退；11-关闭破产→用人单位辞退；12-改制→其他原因中断缴费；13-隶属关系转移→工作关系调转；14-双方协商一致本人解除→个人原因解除；15-双方协商一致单位解除→用人单位辞退；16-退休→人员达到享受养老待遇条件

  **Must NOT do**:
  - 不把字典/映射写死在生成器代码里（生成器只读 DB）
  - 不删减社保增员模板 27 列中的任何列定义

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需精确对照 6 个模板的列结构与字典值，领域性强
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 T3、T5 并行）
  - **Blocks**: T6-T12
  - **Blocked By**: T2

  **References**:
  - 列结构：读 `/home/ubuntu/coding/SI-Batch/输入输出/输入/合同批量导入模板 (增员).xls`、`合同解除批量导入模板 (减员).xls`
  - 输出列结构：读 `输入输出/输出/社保失业工伤/企业职工批量参保登记模板 -20260902-1227(增员).xlsx`（27 列）、`单位职工停保模板-20260907-0932-1人(减员).xlsx`、`输入输出/输出/医保/001 批量职工新参保(增员).xls`（17 列）、`批量减员申报(减员).xls`
  - 字典值：增员表「二级代码」「发放银行」sheet、减员表「Sheet2」

  **Acceptance Criteria**:
  - [ ] `python -c "import db; db.seed_data()"` 无报错
  - [ ] `sqlite3 si_batch.db "select count(*) from dict_mapping"` 返回 > 20
  - [ ] `select count(*) from mapping_stop_reason` 返回 16
  - [ ] 社保增员列定义共 27 项、医保增员 17 项、社保减员 5 项、医保减员 3 项

  **QA Scenarios**:
  ```
  Scenario: 种子数据齐全
    Tool: Bash
    Steps:
      1. python -c "import db; db.seed_data()"
      2. sqlite3 si_batch.db "select count(*) from mapping_stop_reason; select count(*) from dict_mapping; select count(*) from system_defaults"
    Expected Result: 16 / >20 / >=8
    Failure Indicators: 任一计数为 0
    Evidence: .omo/evidence/task-4-seed.txt
  ```

  **Commit**: YES
  - Message: `feat(config): column constants + dict/mapping/defaults seed data`



---

- [ ] 5. 工具函数（身份证推导/日期转换/前缀剥离）

  **What to do**:
  - 写 `mapping.py`，提供纯函数：
    - `derive_gender(id_card)`：18 位身份证第 17 位（index 16）奇偶 → 男/女（奇数=男）
    - `derive_birthday(id_card)`：第 7-14 位（index 6:14）→ `yyyyMMdd`
    - `yyyymm_to_date(yyyymm)`：`202006` → `20200601`（补 `01`）
    - `dash_date_to_yyyymmdd(s)`：`2019-03-03` → `20190303`（去横线）
    - `to_excel_serial(date_str_yyyymmdd)`：→ Excel 1900 序列号（`(date - datetime(1899,12,30)).days`，浮点数，如 `20260701` → `46204.0`）
    - `strip_prefix(value)`：`01-汉族` → `汉族`（取最后一个 `-` 之后）
  - 全部无副作用、可独立 import 测试

  **Must NOT do**:
  - 不处理 15 位老身份证（输入说明「18 位准确号码」；15 位直接标记为校验错误）
  - 非身份证证件（证件类型=9）时 `derive_gender/derive_birthday` 返回 None 而非报错

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 身份证校验位/出生日期/Excel 序列号历元逻辑易错，需仔细
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 T1、T2 并行）
  - **Blocks**: T6-T12
  - **Blocked By**: None

  **References**:
  - Excel 1900 序列号：已知 `39070.0`=`2006-12-19`、`46204.0`=`2026-07-01`（医保增员模板样本）
  - 身份证规则：第 7-14 位出生日期、第 17 位性别、第 18 位可为 X

  **Acceptance Criteria**:
  - [ ] `derive_gender('220101198001010059')` → `男`；`derive_gender('22010419961122754X')` → `女`（第17位=4偶）
  - [ ] `derive_birthday('220101198001010059')` → `19800101`
  - [ ] `to_excel_serial('20061219')` → `39070.0`；`to_excel_serial('20260701')` → `46204.0`
  - [ ] `strip_prefix('01-汉族')` → `汉族`；`yyyymm_to_date('202006')` → `20200601`

  **QA Scenarios**:
  ```
  Scenario: 身份证推导与日期序列号
    Tool: Bash
    Steps:
      1. python -c "from mapping import *; print(derive_gender('220101198001010059'), derive_birthday('220101198001010059'), to_excel_serial('20061219'), strip_prefix('01-汉族'))"
    Expected Result: 男 19800101 39070.0 汉族
    Failure Indicators: 任一值不符
    Evidence: .omo/evidence/task-5-derive.txt
  ```

  **Commit**: YES
  - Message: `feat(util): idcard derive + date convert + prefix strip`

- [ ] 6. 增员表解析器（60列 .xls → 结构化记录 + 校验 + 入库）

  **What to do**:
  - 写 `parser/enroll_parser.py`：用 xlrd 读 `.xls`，取 Sheet1，数据从第 5 行（0 索引 row 4）开始（前 4 行：注意事项/分组头/列名/格式说明）
  - 按 T4 定义的列常量解析 60 列，提取关键字段：姓名、身份证号码、民族、人员身份、户口性质、联系电话、合同开始时间、合同工资、是否参加养老/失业/医疗/工伤/生育、社保参保属地、社保参保年月、医保参保属地、医保参保年月、各缴费基数、工资账号、发放银行、证件类型 等
  - 校验必录项：姓名、身份证号码非空；身份证 18 位；其余可选
  - 结果结构化存储：写入 `import_batches` + `enroll_records`（raw_json 存完整行 + 关键字段单独列便于查询）
  - 返回解析结果（成功条数/失败原因列表）

  **Must NOT do**:
  - 不做字段到输出的映射（映射在生成器 T8/T11 读 DB 完成）
  - 身份证/工资账号等一律按文本读取，不做数字转换（防精度丢失）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 60 列解析 + 校验 + 文本保真，逻辑密集
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2（与 T7-T12 并行）
  - **Blocks**: T13、T14、T16
  - **Blocked By**: T4、T5

  **References**:
  - 输入模板：`输入输出/输入/合同批量导入模板 (增员).xls`（Sheet1 60 列，R4 为张三样本）
  - 字典 sheet：同文件「二级代码」「发放银行」

  **Acceptance Criteria**:
  - [ ] 解析张三样本行：姓名=张三、身份证=220101198001010059、合同工资=2500
  - [ ] 身份证/工资账号读为文本（`6200000000000000` 不丢精度）
  - [ ] 缺姓名的行计入失败原因

  **QA Scenarios**:
  ```
  Scenario: 解析真实增员模板
    Tool: Bash
    Steps:
      1. python -c "from parser.enroll_parser import parse; r=parse('输入输出/输入/合同批量导入模板 (增员).xls'); print(len(r['records']), r['records'][0]['name'])"
    Expected Result: 打印 >=1 张三
    Failure Indicators: 报错或 records 为空
    Evidence: .omo/evidence/task-6-parse.txt

  Scenario: 文本保真（16位工资账号）
    Tool: Bash
    Steps:
      1. python -c "from parser.enroll_parser import parse; r=parse('输入输出/输入/合同批量导入模板 (增员).xls'); print(r['records'][0]['salary_account'])"
    Expected Result: 6200000000000000（16 位完整，非科学计数）
    Evidence: .omo/evidence/task-6-precision.txt
  ```

  **Commit**: YES
  - Message: `feat(parser): enroll table parser`

- [ ] 7. 减员表解析器（16列 .xls → 结构化记录 + 入库）

  **What to do**:
  - 写 `parser/reduce_parser.py`：xlrd 读 `.xls`，Sheet1 16 列，数据从第 5 行开始
  - 提取字段：姓名、身份证号码、合同终止日期、社保报减年月、医保报减年月、工伤报减年月、合同终止原因、是否享受失业金、工资结束年月、是否经济赔偿、备注、社保/医保参保状态
  - 校验：姓名、身份证号码非空
  - 写入 `import_batches` + `reduce_records`

  **Must NOT do**:
  - 不处理公积金报减年月（公积金 out of scope，字段忽略）
  - 身份证按文本读

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 16 列解析，逻辑较增员简单
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2（与 T6、T8-T12 并行）
  - **Blocks**: T13、T14、T16
  - **Blocked By**: T4、T5

  **References**:
  - 输入模板：`输入输出/输入/合同解除批量导入模板 (减员).xls`（Sheet1 16 列，R4 张三样本）
  - 合同终止原因字典：同文件 Sheet2

  **Acceptance Criteria**:
  - [ ] 解析张三样本：姓名=张三、身份证=220101198001010059、合同终止原因=01-在试用期被证明不符合录用条件
  - [ ] 缺姓名行计入失败原因

  **QA Scenarios**:
  ```
  Scenario: 解析真实减员模板
    Tool: Bash
    Steps:
      1. python -c "from parser.reduce_parser import parse; r=parse('输入输出/输入/合同解除批量导入模板 (减员).xls'); print(len(r['records']), r['records'][0]['name'], r['records'][0]['terminate_reason'])"
    Expected Result: 打印 >=1 张三 01-在试用期被证明不符合录用条件
    Failure Indicators: 报错或 records 为空
    Evidence: .omo/evidence/task-7-parse.txt
  ```

  **Commit**: YES
  - Message: `feat(parser): reduce table parser`

- [ ] 8. 社保增员生成器（.xlsx 27列 复制模板结构）

  **What to do**:
  - 写 `generator/social_enroll.py`：openpyxl 打开原模板 `输入输出/输出/社保失业工伤/企业职工批量参保登记模板 -20260902-1227(增员).xlsx` 作为底稿（保留 R0 说明、R1 单位编号/名称/参保险种、R2 列名、R3 示例行「小明」及合并单元格），从第 5 行（1 索引）开始写数据
  - 27 列映射（读 DB 字典 + 工具函数）：
    - 证件类型=字典映射(证件类型)；证件号码=身份证；姓名=姓名
    - 民族=strip_prefix；性别=derive_gender；出生日期=derive_birthday
    - 参加工作日期=合同开始时间(dash→yyyymmdd)；国籍=默认(中国)；农民工标识=默认(非农民工)
    - 人员身份=字典映射；临时账户标识=默认(一般账户)
    - 申报工资=合同工资；参保日期=合同开始时间
    - 企业养老/失业保险/工伤保险=是否参加养老/失业/工伤(1-是→是)
    - 是否兼职工伤=默认(否)；户口所在地址/常住地址=地址；工作所在地址=社保参保属地→字典映射
    - 联系电话=联系电话；参保身份=默认(企业职工)；模板版本=1.0
  - 单位编号/名称从 `unit_config`(social) 读入 R1
  - 只包含「社保属地」为市社保的记录（省工伤不走此报盘）

  **Must NOT do**:
  - 不删示例行、不破坏合并单元格、不改列名（含 `*` 前缀与 `外国人永久居留中文名称` 后换行）
  - 不硬编码字典值（读 dict_mapping/system_defaults）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 27 列映射 + 模板结构保真（合并单元格/示例行）是最高风险点
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2（与 T6、T7、T9-T12 并行）
  - **Blocks**: T14
  - **Blocked By**: T4、T5

  **References**:
  - 输出模板：`输入输出/输出/社保失业工伤/企业职工批量参保登记模板 -20260902-1227(增员).xlsx`（人员名单 27 列 A:AA，示例行「小明」在 R4）
  - 列结构以模板 R3 列名为准（含 `*参保日期`、`外国人永久居留中文名称\n`）

  **Acceptance Criteria**:
  - [ ] 用张三样本生成：证件号码=220101198001010059、性别=男、出生日期=19800101、民族=汉族、申报工资=2500
  - [ ] 生成文件 R3 列名与模板一致，R4 示例行保留，数据从 R5 开始
  - [ ] 企业养老/失业/工伤=是/是/是（张三样本 1-是）

  **QA Scenarios**:
  ```
  Scenario: 生成社保增员报盘并回读
    Tool: Bash
    Steps:
      1. 先解析增员模板入库，再 python -c "from generator.social_enroll import generate; generate(batch_id=1, out='outputs/test_social_enroll.xlsx')"
      2. python -c "import openpyxl; wb=openpyxl.load_workbook('outputs/test_social_enroll.xlsx'); ws=wb['人员名单']; print(ws.cell(3,3).value, ws.cell(4,3).value, ws.cell(5,3).value, ws.cell(5,5).value, ws.cell(5,6).value)"
    Expected Result: 姓名(列名) 小明 张三 男 19800101
    Failure Indicators: 示例行缺失、性别/出生日期错、列错位
    Evidence: .omo/evidence/task-8-social-enroll.txt
  ```

  **Commit**: YES
  - Message: `feat(gen): social enroll report generator`

- [ ] 9. 社保减员生成器（.xlsx 5列 + 追加合同终止原因）

  **What to do**:
  - 写 `generator/social_reduce.py`：openpyxl 生成 `.xlsx`，列名与 `单位职工停保模板` 一致
  - 列：证件号码、姓名、停保日期、停保原因、备注，**末尾追加第 6 列「合同终止原因」**（原始值）
  - 映射：停保日期=合同终止日期(dash→yyyymmdd)；停保原因=合同终止原因 → `mapping_stop_reason.social_stop_reason`（9 值字典，读 DB）
  - 只含社保减员记录（有社保报减年月的）

  **Must NOT do**:
  - 停保原因不硬编码，读 DB 映射
  - 不生成省工伤记录（省工伤走 T10）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 5+1 列，映射逻辑中等
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: T14
  - **Blocked By**: T4、T5

  **References**:
  - 输出模板：`输入输出/输出/社保失业工伤/单位职工停保模板-20260907-0932-1人(减员).xlsx`（Sheet1 5 列，Sheet2 九值停保原因字典）
  - 减员原因映射：`mapping_stop_reason` 表

  **Acceptance Criteria**:
  - [ ] 生成文件列：证件号码/姓名/停保日期/停保原因/备注/合同终止原因（6 列）
  - [ ] 张三样本：停保原因=用人单位辞退（01 映射），停保日期=20190101（合同终止日期）

  **QA Scenarios**:
  ```
  Scenario: 生成社保减员报盘并回读
    Tool: Bash
    Steps:
      1. python -c "from generator.social_reduce import generate; generate(batch_id=1, out='outputs/test_social_reduce.xlsx')"
      2. python -c "import openpyxl; wb=openpyxl.load_workbook('outputs/test_social_reduce.xlsx'); ws=wb.active; print(ws.max_column, ws.cell(2,1).value, ws.cell(2,4).value, ws.cell(2,6).value)"
    Expected Result: 6 220101198001010059 用人单位辞退 01-在试用期被证明不符合录用条件
    Failure Indicators: 列数≠6、停保原因映射错、合同终止原因列缺失
    Evidence: .omo/evidence/task-9-social-reduce.txt
  ```

  **Commit**: YES
  - Message: `feat(gen): social reduce report generator`

- [ ] 10. 省工伤减员生成器（.xlsx 停保5列）

  **What to do**:
  - 写 `generator/province_injury_reduce.py`：openpyxl 生成 `.xlsx`，列名与 `单位职工停保模板` 一致（证件号码/姓名/停保日期/停保原因/备注）
  - 数据来源：`province_injury` 表（筛选需减员的记录，即停保日期/停保原因非空）
  - 停保日期=省工伤记录里的停保日期；停保原因=省工伤记录里的停保原因（或映射）
  - 不追加合同终止原因列（省工伤名单无该字段）

  **Must NOT do**:
  - 不从增员/减员批次取数（省工伤来源独立表）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 5 列，逻辑简单但需正确从省工伤表取数
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: T15
  - **Blocked By**: T4、T5

  **References**:
  - 输出模板：`输入输出/输出/社保失业工伤/单位职工停保模板-20260907-0932-1人(减员).xlsx`（5 列结构）
  - 数据表：`province_injury`

  **Acceptance Criteria**:
  - [ ] 生成文件 5 列（证件号码/姓名/停保日期/停保原因/备注）
  - [ ] 只含 province_injury 中停保日期非空的记录

  **QA Scenarios**:
  ```
  Scenario: 生成省工伤减员报盘
    Tool: Bash
    Steps:
      1. 向 province_injury 插入一条测试记录（停保日期=20260701, 停保原因=用人单位辞退）
      2. python -c "from generator.province_injury_reduce import generate; generate(out='outputs/test_pi_reduce.xlsx')"
      3. python -c "import openpyxl; ws=openpyxl.load_workbook('outputs/test_pi_reduce.xlsx').active; print(ws.max_column, ws.cell(2,3).value)"
    Expected Result: 5 20260701
    Failure Indicators: 列数≠5 或数据缺失
    Evidence: .omo/evidence/task-10-pi-reduce.txt
  ```

  **Commit**: YES
  - Message: `feat(gen): province injury reduce generator`

- [ ] 11. 医保增员生成器（.xls 17列 省/市拆分 日期序列号）

  **What to do**:
  - 写 `generator/medical_enroll.py`：用 xlwt 写 `.xls`，列名与 `001 批量职工新参保(增员)` 一致
  - 17 列：证件类型/证件号码/姓名/性别/民族/出生日期/首次参加工作日期/户口性质/婚姻状态/健康状况/居住地址/居住地邮政编码/固定电话/手机号码/申报工资/编制类型/本次参保时间
  - 关键映射与类型：
    - 出生日期/首次参加工作日期/本次参保时间 = **Excel 序列号（float）**，用 `to_excel_serial`
    - 本次参保时间：**省医保=合同开始时间；市医保=医保参保年月+01**
    - 首次参加工作日期=合同开始时间；出生日期=derive_birthday；性别=derive_gender；民族=strip_prefix
    - 户口性质=字典映射（输入户口性质代码 → 医保户口性质值）
    - 婚姻状态/健康状况/编制类型=system_defaults；申报工资=合同工资；手机号码=联系电话（文本）
  - **按医保参保属地拆分成省医保、市医保两个独立文件**（2299...省直→省，2201...→市）
  - 输出文件名区分省/市

  **Must NOT do**:
  - 日期不写文本，写序列号 float（如 `39070.0`）
  - 手机号码/证件号码/身份证写文本，防前导零/科学计数丢失

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: xlwt 写 .xls + 日期序列号 + 省/市拆分，类型易错
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: T16
  - **Blocked By**: T4、T5

  **References**:
  - 输出模板：`输入输出/输出/医保/001 批量职工新参保(增员).xls`（17 列，日期为序列号）
  - 序列号验证：`39070.0`=`2006-12-19`、`46204.0`=`2026-07-01`

  **Acceptance Criteria**:
  - [ ] 生成省、市两个 .xls 文件
  - [ ] 张三样本（医保属地=省直）落入省医保文件，出生日期=序列号 29221.0（19800101）
  - [ ] 手机号码写为文本 `13333333333`

  **QA Scenarios**:
  ```
  Scenario: 生成省/市医保增员并回读
    Tool: Bash
    Steps:
      1. python -c "from generator.medical_enroll import generate; r=generate(batch_id=1, out_dir='outputs'); print(r)"
      2. python -c "import xlrd; wb=xlrd.open_workbook('outputs/省医保增员.xls'); ws=wb.sheet_by_index(0); print(ws.ncols, ws.cell_value(1,2), ws.cell_value(1,5))"
    Expected Result: 17 张三 29221.0（出生日期序列号）
    Failure Indicators: 列数≠17、日期为文本、省/市未拆分
    Evidence: .omo/evidence/task-11-medical-enroll.txt
  ```

  **Commit**: YES
  - Message: `feat(gen): medical enroll generator (province/city split)`

- [ ] 12. 医保减员生成器（.xls 3列 省/市拆分）

  **What to do**:
  - 写 `generator/medical_reduce.py`：xlwt 写 `.xls`，3 列：姓名/证件类型/证件号码
  - 按医保参保属地拆分成省、市两个文件
  - 证件类型=字典映射，证件号码=身份证

  **Must NOT do**:
  - 不追加合同终止原因（医保减员保持 3 列）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 3 列极简
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: T16
  - **Blocked By**: T4、T5

  **References**:
  - 输出模板：`输入输出/输出/医保/批量减员申报(减员).xls`（Sheet1 3 列）

  **Acceptance Criteria**:
  - [ ] 生成省、市两个 .xls，各 3 列
  - [ ] 张三样本落入对应属地文件

  **QA Scenarios**:
  ```
  Scenario: 生成省/市医保减员
    Tool: Bash
    Steps:
      1. python -c "from generator.medical_reduce import generate; print(generate(batch_id=1, out_dir='outputs'))"
      2. python -c "import xlrd; ws=xlrd.open_workbook('outputs/市医保减员.xls').sheet_by_index(0); print(ws.ncols, ws.cell_value(1,0))"
    Expected Result: 3 张三
    Evidence: .omo/evidence/task-12-medical-reduce.txt
  ```

  **Commit**: YES
  - Message: `feat(gen): medical reduce generator (province/city split)`

- [ ] 13. 前台上传页面 + 路由

  **What to do**:
  - 写 `templates/upload.html` + 路由：上传增员表/减员表（.xls），调用 T6/T7 解析器入库
  - 显示解析结果（成功条数、失败原因列表）
  - 批次列表：显示已导入批次（类型/文件名/上传人/时间/条数）
  - 权限：`front`、`admin` 可访问

  **Must NOT do**:
  - 不做报盘生成（那是社保/医保管理员的功能）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 页面布局 + 文件上传交互
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3（与 T14-T19 并行）
  - **Blocks**: T20
  - **Blocked By**: T3、T6、T7

  **References**:
  - base.html（T3）导航结构；解析器 T6/T7 返回格式

  **Acceptance Criteria**:
  - [ ] 上传真实增员模板 → 显示成功条数 ≥1
  - [ ] 上传无姓名行 → 显示失败原因

  **QA Scenarios**:
  ```
  Scenario: 上传增员表
    Tool: Bash (curl)
    Steps:
      1. 登录 front 账号
      2. curl -b /tmp/c.txt -F "file=@输入输出/输入/合同批量导入模板 (增员).xls" -F "type=enroll" http://localhost:5000/upload
    Expected Result: 响应 200，页面含「成功」与条数
    Failure Indicators: 500 / 无结果提示
    Evidence: .omo/evidence/task-13-upload.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): front upload page + routes`

- [ ] 14. 社保管理员页面 + 路由

  **What to do**:
  - 写 `templates/social.html` + 路由：列出增员/减员批次，选择批次 → 调 T8/T9 生成社保增员/社保减员报盘 → 下载
  - 生成记录写入 `output_batches`（insurance_type=social），状态可查看
  - 权限：`social`、`admin`

  **Must NOT do**:
  - 不暴露医保报盘、省工伤报盘入口（省工伤走 T15 页）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 页面 + 生成下载交互
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: T20
  - **Blocked By**: T3、T8、T9

  **References**:
  - base.html 导航；生成器 T8/T9 的 `generate()` 签名

  **Acceptance Criteria**:
  - [ ] 选择增员批次 → 生成并下载社保增员报盘
  - [ ] 选择减员批次 → 生成并下载社保减员报盘（6 列）

  **QA Scenarios**:
  ```
  Scenario: 生成社保报盘并下载
    Tool: Bash (curl)
    Steps:
      1. 登录 social 账号
      2. curl -b /tmp/c.txt http://localhost:5000/social/generate?type=enroll&batch_id=1
      3. curl -b /tmp/c.txt -o /tmp/o.xlsx http://localhost:5000/social/download/1
    Expected Result: 生成接口 200；下载文件非空且为 xlsx
    Failure Indicators: 403（无权限）/ 空文件
    Evidence: .omo/evidence/task-14-social.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): social admin page + routes`

- [ ] 15. 省工伤管理页面 + 路由（CRUD + 导入 + 减员报盘生成）

  **What to do**:
  - 写 `templates/province_injury.html` + 路由：省工伤人员信息表列表 + 新增/编辑/删除
  - 导入省工伤名单（按增员模板 .xls 格式，复用 T6 解析逻辑写入 `province_injury`）
  - 生成省工伤减员报盘（调 T10）→ 下载
  - 字段按增员模板设计（证件号码/姓名/结算单元/合同开始时间等，保留冗余字段）
  - 权限：`social`、`admin`

  **Must NOT do**:
  - 省工伤增员不实现（只减员）
  - 不与其他批次混用数据

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: CRUD 表格 + 导入 + 下载
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: T20
  - **Blocked By**: T3、T10

  **References**:
  - `province_injury` 表结构；生成器 T10

  **Acceptance Criteria**:
  - [ ] 可新增/编辑/删除省工伤记录
  - [ ] 可导入省工伤名单文件
  - [ ] 可生成并下载省工伤减员报盘（5 列）

  **QA Scenarios**:
  ```
  Scenario: 省工伤 CRUD + 生成报盘
    Tool: Bash (curl)
    Steps:
      1. 登录 social 账号
      2. curl -b /tmp/c.txt -d "name=测试&id_card=220101199001011234&..." http://localhost:5000/province_injury/add
      3. curl -b /tmp/c.txt http://localhost:5000/province_injury/generate
    Expected Result: 新增成功；生成接口 200
    Evidence: .omo/evidence/task-15-pi.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): province injury management page + routes`

- [ ] 16. 医保管理员页面 + 路由

  **What to do**:
  - 写 `templates/medical.html` + 路由：列出增员/减员批次
  - 增员批次 → 调 T11 生成省医保增员 + 市医保增员两个文件 → 分别下载
  - 减员批次 → 调 T12 生成省医保减员 + 市医保减员两个文件 → 分别下载
  - 权限：`medical`、`admin`

  **Must NOT do**:
  - 不暴露社保报盘入口

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 页面 + 省/市双文件生成下载
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: T20
  - **Blocked By**: T3、T11、T12

  **References**:
  - 生成器 T11/T12；base.html

  **Acceptance Criteria**:
  - [ ] 增员批次 → 生成省、市医保增员两个 .xls 并可下载
  - [ ] 减员批次 → 生成省、市医保减员两个 .xls 并可下载

  **QA Scenarios**:
  ```
  Scenario: 生成省/市医保报盘并下载
    Tool: Bash (curl)
    Steps:
      1. 登录 medical 账号
      2. curl -b /tmp/c.txt http://localhost:5000/medical/generate?type=enroll&batch_id=1
      3. curl -b /tmp/c.txt -o /tmp/m.xls http://localhost:5000/medical/download/1
    Expected Result: 生成 200；下载 .xls 非空
    Evidence: .omo/evidence/task-16-medical.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): medical admin page + routes`

- [ ] 17. admin 用户管理页面 + 路由

  **What to do**:
  - 写 `templates/admin_users.html` + 路由：用户列表 + 新增/编辑/删除（用户名、密码、角色、显示名）
  - 角色下拉：前台业务员/社保管理员/医保管理员/admin
  - 密码哈希存储
  - 权限：`admin` 专属

  **Must NOT do**:
  - 不实现自助注册

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准 CRUD 页面
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: T20
  - **Blocked By**: T3

  **References**:
  - auth.py 角色常量、users 表

  **Acceptance Criteria**:
  - [ ] 可新增社保管理员账号并成功登录
  - [ ] 可删除账号

  **QA Scenarios**:
  ```
  Scenario: 新增用户并登录
    Tool: Bash (curl)
    Steps:
      1. 登录 admin
      2. curl -b /tmp/c.txt -d "username=test_social&password=123456&role=social" http://localhost:5000/admin/users/add
      3. curl -d "username=test_social&password=123456" http://localhost:5000/login
    Expected Result: 新增 200；新账号登录成功
    Evidence: .omo/evidence/task-17-users.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): admin user management`

- [ ] 18. admin 单位信息配置页面 + 路由

  **What to do**:
  - 写 `templates/admin_units.html` + 路由：编辑 `unit_config`（社保单位编号/名称、医保单位编号/名称）
  - 生成报盘时读此配置填入模板（社保增员 R1 单位编号/名称）
  - 权限：`admin`

  **Must NOT do**:
  - 不硬编码单位信息

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单配置表单
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: T20
  - **Blocked By**: T3

  **References**:
  - unit_config 表；社保增员模板 R1 单位编号/名称

  **Acceptance Criteria**:
  - [ ] 保存社保单位编号/名称后，生成社保增员报盘 R1 正确填入

  **QA Scenarios**:
  ```
  Scenario: 配置单位信息并验证生成
    Tool: Bash (curl)
    Steps:
      1. 登录 admin
      2. curl -b /tmp/c.txt -d "social_code=123456&social_name=测试公司" http://localhost:5000/admin/units/save
      3. 生成社保增员报盘，读 R1 单位编号
    Expected Result: R1 单位编号=123456
    Evidence: .omo/evidence/task-18-units.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): admin unit config`

- [ ] 19. admin 映射/字典/默认值配置页面 + 路由

  **What to do**:
  - 写 `templates/admin_mappings.html` + 路由，三个 Tab 或分区：
    - 减员原因映射（mapping_stop_reason）：合同终止原因 → 社保停保原因
    - 字典映射（dict_mapping）：民族/户口性质/人员身份/证件类型/属地→工作地址
    - 默认值（system_defaults）：婚姻状态/健康状况/编制类型/国籍等
  - 全部可增删改，生成器读 DB 生效
  - 权限：`admin`

  **Must NOT do**:
  - 不把字典/映射写死在代码

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 配置 CRUD
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: T20
  - **Blocked By**: T3

  **References**:
  - mapping_stop_reason / dict_mapping / system_defaults 表（T2/T4 预置种子）

  **Acceptance Criteria**:
  - [ ] 修改某减员原因映射后，重新生成社保减员报盘停保原因随之变化

  **QA Scenarios**:
  ```
  Scenario: 改映射后生成生效
    Tool: Bash (curl)
    Steps:
      1. 登录 admin
      2. curl -b /tmp/c.txt -d "source=01-在试用期被证明不符合录用条件&social=其他原因中断缴费" http://localhost:5000/admin/mappings/save
      3. 重新生成社保减员报盘，读停保原因
    Expected Result: 停保原因=其他原因中断缴费
    Evidence: .omo/evidence/task-19-mappings.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): admin mappings config`

- [ ] 20. 首页仪表盘 + 路由整合 + 权限联调

  **What to do**:
  - 写 `templates/dashboard.html`：按角色显示待办（前台=待上传、社保=待生成社保/省工伤、医保=待生成医保、admin=管理入口）
  - 整合全部蓝图/路由到 app.py，统一登录重定向（按角色跳转首页）
  - 权限装饰器全覆盖，越权返回 403
  - base.html 导航按角色显隐菜单

  **Must NOT do**:
  - 不做复杂统计图表（简单计数即可）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 集成联调，权限正确性关键
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: NO（依赖 T13-T19 全部路由）
  - **Parallel Group**: Wave 4
  - **Blocks**: T21
  - **Blocked By**: T13-T19

  **References**:
  - 各页面路由（T13-T19）、auth.py 装饰器

  **Acceptance Criteria**:
  - [ ] 四角色登录后分别看到对应菜单与首页内容
  - [ ] 前台访问 /social/* 返回 403；社保访问 /medical/* 返回 403

  **QA Scenarios**:
  ```
  Scenario: 权限隔离联调
    Tool: Bash (curl)
    Steps:
      1. 分别用 front/social/medical/admin 登录
      2. front 访问 /social/generate → 403
      3. social 访问 /medical/generate → 403
      4. medical 访问 /social/generate → 403
    Expected Result: 均 403
    Evidence: .omo/evidence/task-20-rbac.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): dashboard + route integration + RBAC wiring`

- [ ] 21. 部署文档 + README + 启动脚本 + 局域网访问说明

  **What to do**:
  - 写 `README.md`：安装（venv + pip install -r）、初始化（建表+种子）、启动、默认账号、局域网访问
  - 写 `run.sh`：一键启动（激活 venv、初始化 DB、python app.py）
  - 局域网说明：监听 0.0.0.0:5000，防火墙放行 5000 端口，其他电脑访问 `http://<服务器IP>:5000`

  **Must NOT do**:
  - 不写自动化部署（systemd/docker 可选，不强制）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 文档
  - **Skills**: 无

  **Parallelization**:
  - **Can Run In Parallel**: NO（最后）
  - **Parallel Group**: Wave 4
  - **Blocks**: None
  - **Blocked By**: T20

  **References**:
  - config.py 端口/路径、db.py init/seed、auth.py 默认账号

  **Acceptance Criteria**:
  - [ ] `./run.sh` 一键启动成功
  - [ ] README 含默认账号密码、局域网访问步骤

  **QA Scenarios**:
  ```
  Scenario: 一键启动
    Tool: Bash
    Steps:
      1. ./run.sh（后台运行）
      2. curl http://localhost:5000/login
    Expected Result: 200，返回登录页
    Evidence: .omo/evidence/task-21-run.txt
  ```

  **Commit**: YES
  - Message: `docs(deploy): README + startup script + LAN access`

## Final Verification Wave (MANDATORY — 所有实现任务之后)

- [ ] F1. **Plan Compliance Audit** — `oracle`
  通读计划，逐项核对「Must Have」是否实现（读文件、curl 接口、跑命令），逐项检查「Must NOT Have」是否违规（搜代码库禁用模式，file:line 举证）。检查 `.omo/evidence/` 证据文件齐全。对比交付物与计划。
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  跑计划「Success Criteria」里的启动/自检命令。审查所有变更文件：类型抑制、空 catch、调试日志、注释掉的代码、未用 import。检查 AI 味代码：过度注释、过度抽象、泛化命名（data/result/item/temp）。
  Output: `Startup [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`（+ playwright 若 UI）
  从干净状态启动，执行每个任务的全部 QA 场景——严格按步骤，留证据。测跨任务集成（导入→生成→下载全链路）。测边界：空文件、非法身份证、缺必录项、越权访问。证据存 `.omo/evidence/final-qa/`。
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  对每个任务：读「What to do」、读实际 diff（git log/diff）。逐条核对 1:1——该建的都建了（无缺失），不该建的没建（无蔓延）。检查「Must NOT do」合规。检测跨任务污染。标记未记录变更。
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

> 项目初始非 git 仓库，T1 中 `git init`。每任务独立原子提交。

- **1**: `chore(init): project skeleton, venv, deps, flask entry` - requirements.txt, app.py, config.py
- **2**: `feat(db): sqlite schema for all tables` - db.py
- **3**: `feat(auth): login/logout/session/role decorators` - auth.py, templates/login.html, templates/base.html
- **4**: `feat(config): column constants + dict/mapping/defaults seed data` - config.py, db.py
- **5**: `feat(util): idcard derive + date convert + prefix strip` - mapping.py
- **6**: `feat(parser): enroll table parser` - parser/enroll_parser.py
- **7**: `feat(parser): reduce table parser` - parser/reduce_parser.py
- **8**: `feat(gen): social enroll report generator` - generator/social_enroll.py
- **9**: `feat(gen): social reduce report generator` - generator/social_reduce.py
- **10**: `feat(gen): province injury reduce generator` - generator/province_injury_reduce.py
- **11**: `feat(gen): medical enroll generator (province/city split)` - generator/medical_enroll.py
- **12**: `feat(gen): medical reduce generator (province/city split)` - generator/medical_reduce.py
- **13**: `feat(ui): front upload page + routes` - templates/upload.html
- **14**: `feat(ui): social admin page + routes` - templates/social.html
- **15**: `feat(ui): province injury management page + routes` - templates/province_injury.html
- **16**: `feat(ui): medical admin page + routes` - templates/medical.html
- **17**: `feat(ui): admin user management` - templates/admin_users.html
- **18**: `feat(ui): admin unit config` - templates/admin_units.html
- **19**: `feat(ui): admin mappings config` - templates/admin_mappings.html
- **20**: `feat(ui): dashboard + route integration + RBAC wiring` - templates/dashboard.html
- **21**: `docs(deploy): README + startup script + LAN access` - README.md, run.sh

---

## Success Criteria

### Verification Commands
```bash
# 启动
cd /home/ubuntu/coding/SI-Batch && source .venv/bin/activate && python app.py
# 预期：Listening on 0.0.0.0:5000

# 自检：用真实模板跑通解析+生成
python -c "from parser.enroll_parser import parse; print(parse('输入输出/输入/合同批量导入模板 (增员).xls'))"
# 预期：返回结构化记录列表，含张三样本
```

### Final Checklist
- [ ] 四角色登录分权正确，越权访问被拒
- [ ] 增员/减员导入解析成功，必录项校验生效
- [ ] 7 种报盘按精确模板结构生成（社保增员保留示例行+合并单元格，医保日期为序列号）
- [ ] 省工伤信息表可导入/查看/编辑/删除
- [ ] 减员原因映射、单位信息、字典、默认值后台可改并生效
- [ ] 数字精度：16 位工资账号、X 后缀身份证导入导出不变
- [ ] 局域网可访问
