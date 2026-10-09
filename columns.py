"""Column constants for all six import/export templates of SI-Batch.

STRUCTURE ONLY — this file contains NO business dictionary values, mappings,
or defaults. All business rules (民族/户口性质/人员身份/证件类型/属地 mappings,
减员原因映射, 默认值) live in the SQLite DB, seeded by db.seed_data() and
editable via the admin backend.

All column indices are 0-based. Header names are kept byte-exact from the
templates (including '*' required-field markers and embedded newlines).

Verified against the real template files (see .omo/evidence/task-4-seed.txt):
  - 输入/合同批量导入模板 (增员).xls                    Sheet1  = 60 cols
  - 输入/合同解除批量导入模板 (减员).xls                  Sheet1  = 16 cols
  - 输出/社保失业工伤/企业职工批量参保登记模板 (增员).xlsx  人员名单 = 27 cols
  - 输出/社保失业工伤/单位职工停保模板 (减员).xlsx         Sheet1  =  5 cols
  - 输出/医保/001 批量职工新参保(增员).xls                Sheet1  = 17 cols
  - 输出/医保/批量减员申报(减员).xls                     Sheet1  =  3 cols
"""

# =====================================================================
# INPUT 1: 合同批量导入模板 (增员).xls
# =====================================================================
# Sheet layout (0-based rows):
#   R0 = 注意事项 (merged instructions)
#   R1 = 分组头 (员工基本信息 / 历史数据补录选填 / 意外险维护 / 保险跨年补缴录入 / 非身份证录入)
#   R2 = 列名 (60 columns)
#   R3 = 格式说明 (per-column fill instructions)
#   R4 = 数据起始行 (R4 = 张三 sample row)
ENROLL_INPUT_FILE = "输入输出/输入/合同批量导入模板 (增员).xls"
ENROLL_INPUT_SHEET = "Sheet1"
ENROLL_INPUT_HEADER_ROW = 2        # 0-based index of the column-name row
ENROLL_INPUT_DATA_START_ROW = 4    # 0-based index of the first data row
ENROLL_INPUT_COLUMN_COUNT = 60

# Auxiliary dictionary/bank sheets shipped inside the same workbook.
ENROLL_INPUT_DICT_SHEET = "二级代码"    # 户籍所在地/户口性质/民族/学历/人员身份/... dropdown source
ENROLL_INPUT_BANK_SHEET = "发放银行"    # 发放银行 dropdown source

ENROLL_INPUT_COLUMNS = {
    "姓名": 0,                        # 50个汉字以内
    "身份证号码": 1,                  # 18位准确的号码 (text)
    "民族": 2,                        # e.g. 01-汉族 (「二级代码」)
    "学历": 3,                        # e.g. 11-博士研究生 (「二级代码」)
    "地址": 4,
    "身份证有效期": 5,                # yyyy-mm-dd
    "人员身份": 6,                    # e.g. 91-干部 (「二级代码」)
    "员工号": 7,
    "户口性质": 8,                    # e.g. 11-本市城镇户口 (「二级代码」)
    "是否存在职业病危害": 9,
    "招工性质": 10,                   # (「二级代码」)
    "用工性质": 11,                   # e.g. 1-派遣 (「二级代码」)
    "联系电话": 12,                   # 11位数字 (text)
    "部门": 13,
    "档案号": 14,
    "用工方式": 15,                   # (「二级代码」)
    "协议首签日期": 16,               # yyyy-mm-dd
    "合同类型": 17,                   # (「二级代码」)
    "合同开始时间": 18,               # yyyy-mm-dd
    "合同终止时间": 19,               # yyyy-mm-dd
    "合同工资": 20,                   # 10位整数2位小数 (text)
    "工时制度": 21,                   # (「二级代码」)
    "岗位": 22,
    "是否签订退休三方协议": 23,
    "资料提交年月": 24,               # yyyymm
    "是否个人社保单位承担": 25,
    "单位服务费月标准（元/人）": 26,
    "个人承担服务费月标准（元/人）": 27,
    "是否参加工会": 28,               # (「二级代码」)
    "工会会费扣除": 29,               # (「二级代码」)
    "是否参加养老保险": 30,           # 1-是 / 0-否
    "是否参加失业保险": 31,           # 1-是 / 0-否
    "社保参保属地": 32,               # e.g. 220100000000-吉林省长春市 (「二级代码」)
    "社保参保年月": 33,               # yyyymm / 不参保
    "是否参加医疗保险": 34,           # 1-是 / 0-否
    "是否参加工伤保险": 35,           # 1-是 / 0-否
    "是否参加生育保险": 36,           # 1-是 / 0-否
    "医保参保属地": 37,               # e.g. 229900000000-吉林省省直
    "医保参保年月": 38,               # yyyymm / 不参保
    "是否缴纳公积金": 39,
    "公积金参保属地": 40,
    "公积金参保年月": 41,
    "默认公积金比例（%）": 42,        # e.g. 12:7 (「二级代码」)
    "养老缴费基数": 43,
    "失业缴费基数": 44,
    "医保缴费基数": 45,
    "工伤缴费基数": 46,
    "生育缴费基数": 47,
    "公积金缴费基数": 48,
    "备注": 49,
    "工资账号": 50,                   # 16位整数 (text, 防精度丢失)
    "发放银行": 51,                   # e.g. 02000-建设银行 (「发放银行」)
    "社保参保状态": 52,               # (「二级代码」)
    "公积金参保状态": 53,
    "医保参保状态": 54,
    "意外险开始日期": 55,             # 历史数据补录选填
    "意外险结束日期": 56,
    "意外险额度": 57,
    "跨年缴费基数标识": 58,
    "证件类型": 59,                   # 空=居民身份证; 使用身份证证外的证件填写9
}
assert len(ENROLL_INPUT_COLUMNS) == ENROLL_INPUT_COLUMN_COUNT == 60
ENROLL_INPUT_HEADERS = tuple(ENROLL_INPUT_COLUMNS.keys())  # column order

# =====================================================================
# INPUT 2: 合同解除批量导入模板 (减员).xls
# =====================================================================
# Sheet layout (0-based rows):
#   R0 = 注意事项
#   R1 = 分组头 (员工基本信息 / 历史数据补录选填)
#   R2 = 列名 (16 columns)
#   R3 = 格式说明
#   R4 = 数据起始行 (R4 = 张三 sample row)
# Sheet2 = 合同终止原因 / 是-否 / 参保状态 dictionary (17 entries: 01..17)
REDUCE_INPUT_FILE = "输入输出/输入/合同解除批量导入模板 (减员).xls"
REDUCE_INPUT_SHEET = "Sheet1"
REDUCE_INPUT_HEADER_ROW = 2
REDUCE_INPUT_DATA_START_ROW = 4
REDUCE_INPUT_COLUMN_COUNT = 16
REDUCE_INPUT_DICT_SHEET = "Sheet2"  # 合同终止原因 → 是/否 → 参保状态

REDUCE_INPUT_COLUMNS = {
    "姓名": 0,
    "身份证号码": 1,                  # 18位准确的号码 (text)
    "合同终止日期": 2,                # yyyy-mm-dd
    "资料提交年月": 3,                # yyyymm
    "社保报减年月\n(不减社保不用填写)": 4,   # yyyymm
    "公积金报减年月\n(不减公积金不用填写)": 5,  # yyyymm (本系统不处理公积金)
    "医保报减年月\n(不减医保不用填写)": 6,   # yyyymm
    "工伤报减年月\n(不减工伤不用填写)": 7,   # yyyymm
    "合同终止原因": 8,                # e.g. 01-在试用期被证明不符合录用条件 (Sheet2)
    "是否享受失业金": 9,              # 1-是 / 0-否 (Sheet2)
    "工资结束年月（填几月发放到几月）": 10,  # yyyymm
    "是否经济赔偿": 11,               # 1-是 / 0-否
    "备注": 12,
    "社保参保状态": 13,               # (Sheet2)
    "公积金参保状态": 14,
    "医保参保状态": 15,
}
assert len(REDUCE_INPUT_COLUMNS) == REDUCE_INPUT_COLUMN_COUNT == 16
REDUCE_INPUT_HEADERS = tuple(REDUCE_INPUT_COLUMNS.keys())

# =====================================================================
# OUTPUT 1: 企业职工批量参保登记模板 (增员).xlsx — 社保失业工伤
# =====================================================================
# Sheet 「人员名单」 layout (1-based rows, openpyxl):
#   R1 = 说明 (merged A1:U1)
#   R2 = 单位编号: / 单位名称: / *参 保 险 种 (merged C2:D2, N2:P2, R2:U2)
#   R3 = 列名 (27 columns, A..AA; '*' = 必录)
#   R4 = 示例行「小明」(MUST be preserved by the generator)
#   R5 = 数据起始行 (data written from 1-based row 5)
# Merged ranges (structure the generator must keep):
#   A1:U1, C2:D2, N2:P2, R2:U2
# Sheet 「代码」 = output-side dictionaries (证件类型/民族/性别/户口性质/国籍/
#   农民工标识/退役军人标识/临时账户标识/文化程度/是否兼职工伤/人员身份/
#   退役军人类别/军队转业干部级别/参保险种/工作地址)
SOCIAL_ENROLL_OUTPUT_FILE = "输入输出/输出/社保失业工伤/企业职工批量参保登记模板 -20260902-1227(增员).xlsx"
SOCIAL_ENROLL_OUTPUT_SHEET = "人员名单"
SOCIAL_ENROLL_OUTPUT_DICT_SHEET = "代码"
SOCIAL_ENROLL_OUTPUT_HEADER_ROW_1BASED = 3       # column-name row
SOCIAL_ENROLL_OUTPUT_SAMPLE_ROW_1BASED = 4       # 小明 example row (keep!)
SOCIAL_ENROLL_OUTPUT_DATA_START_ROW_1BASED = 5   # first writable data row
SOCIAL_ENROLL_OUTPUT_COLUMN_COUNT = 27
SOCIAL_ENROLL_OUTPUT_MERGED_RANGES = ("A1:U1", "C2:D2", "N2:P2", "R2:U2")

SOCIAL_ENROLL_OUTPUT_COLUMNS = {
    "*证件类型": 0,                              # 输出值: 居民身份证（户口簿）等 (「代码」sheet)
    "*证件号码": 1,                              # 身份证 (text)
    "*姓名": 2,
    "*民族": 3,                                  # e.g. 汉族 (前缀剥离/字典)
    "*性别": 4,                                  # 身份证第17位推导
    "*出生日期": 5,                              # yyyymmdd (身份证第7-14位推导)
    "*参加工作日期": 6,                          # = 合同开始时间 yyyy-mm-dd → yyyymmdd
    "*国籍": 7,                                  # 默认: 中国
    "农民工标识": 8,                             # 默认: 非农民工
    "*人员身份": 9,                             # 字典: 91→职员, 92→企业职工
    "临时账户标识": 10,                          # 默认: 一般账户
    "*申报工资": 11,                            # = 合同工资
    "*参保日期": 12,                            # = 合同开始时间
    "企业养老": 13,                             # 是否参加养老保险 1-是→是
    "失业保险": 14,                             # 是否参加失业保险
    "工伤保险": 15,                             # 是否参加工伤保险
    "是否兼职工伤": 16,                          # 默认: 否
    "户口所在地址": 17,                         # = 地址
    "常住地址": 18,                              # = 地址
    "*工作所在地址": 19,                         # 社保参保属地 → 字典 (220100000000→长春市市本级)
    "*联系电话": 20,
    "参保身份": 21,                              # 默认: 企业职工
    "实际工作单位编号": 22,
    "实际工作单位名称": 23,
    "实际工作单位统一社会信用代码": 24,
    "外国人永久居留中文名称\n": 25,             # 列名含尾部换行 (byte-exact)
    "模板版本": 26,                              # 默认: 1.0
}
assert len(SOCIAL_ENROLL_OUTPUT_COLUMNS) == SOCIAL_ENROLL_OUTPUT_COLUMN_COUNT == 27
SOCIAL_ENROLL_OUTPUT_HEADERS = tuple(SOCIAL_ENROLL_OUTPUT_COLUMNS.keys())

# =====================================================================
# OUTPUT 2: 单位职工停保模板 (减员).xlsx — 社保失业工伤
# =====================================================================
# Sheet1: R1 = 列名 (5 cols), R2 = 数据起始行.
# Sheet2 = 停保原因字典 (9 values: 个人原因解除/用人单位辞退/工作关系调转/
#   人员达到享受养老待遇条件/死亡/到龄停保/人员被判刑收监执行/无附件停保/
#   其他原因中断缴费) — 与 mapping_stop_reason.social_stop_reason 对应.
# 生成器在末尾追加第 6 列「合同终止原因」(原始输入值), 共 6 列.
SOCIAL_REDUCE_OUTPUT_FILE = "输入输出/输出/社保失业工伤/单位职工停保模板-20260907-0932-1人(减员).xlsx"
SOCIAL_REDUCE_OUTPUT_SHEET = "Sheet1"
SOCIAL_REDUCE_OUTPUT_DICT_SHEET = "Sheet2"  # 9 停保原因值
SOCIAL_REDUCE_OUTPUT_HEADER_ROW_1BASED = 1
SOCIAL_REDUCE_OUTPUT_DATA_START_ROW_1BASED = 2
SOCIAL_REDUCE_OUTPUT_COLUMN_COUNT = 5
SOCIAL_REDUCE_OUTPUT_APPEND_COLUMN = "合同终止原因"  # 生成器追加的第 6 列

SOCIAL_REDUCE_OUTPUT_COLUMNS = {
    "证件号码": 0,
    "姓名": 1,
    "停保日期": 2,       # = 合同终止日期 yyyy-mm-dd → yyyymmdd
    "停保原因": 3,       # = 合同终止原因 → mapping_stop_reason.social_stop_reason
    "备注": 4,
}
assert len(SOCIAL_REDUCE_OUTPUT_COLUMNS) == SOCIAL_REDUCE_OUTPUT_COLUMN_COUNT == 5
SOCIAL_REDUCE_OUTPUT_HEADERS = tuple(SOCIAL_REDUCE_OUTPUT_COLUMNS.keys())

# =====================================================================
# OUTPUT 3: 001 批量职工新参保(增员).xls — 医保
# =====================================================================
# Sheet1: R0 = 列名 (17 cols), R1 = 数据起始行.
# 日期列 (出生日期/首次参加工作日期/本次参保时间) 为 Excel 序列号 (float),
# 非文本 — 生成器须写序列号 (见 mapping.to_excel_serial).
# Sheet2/Sheet3 = 空.
# 按医保参保属地拆分: 2299…(省直)→省医保文件, 2201…(长春市)→市医保文件.
MEDICAL_ENROLL_OUTPUT_FILE = "输入输出/输出/医保/001 批量职工新参保(增员).xls"
MEDICAL_ENROLL_OUTPUT_SHEET = "Sheet1"
MEDICAL_ENROLL_OUTPUT_HEADER_ROW = 0        # 0-based: 列名在第 1 行
MEDICAL_ENROLL_OUTPUT_DATA_START_ROW = 1    # 0-based: 数据从第 2 行开始
MEDICAL_ENROLL_OUTPUT_COLUMN_COUNT = 17

MEDICAL_ENROLL_OUTPUT_COLUMNS = {
    "证件类型": 0,                  # 字典: 空→居民身份证（户口簿）
    "证件号码": 1,                  # 身份证 (text)
    "姓名": 2,
    "性别": 3,                      # 身份证推导
    "民族": 4,                      # 前缀剥离/字典
    "出生日期": 5,                  # Excel 序列号 (float), 如 39070.0
    "首次参加工作日期": 6,          # Excel 序列号; = 合同开始时间
    "户口性质": 7,                  # 字典: 输入户口性质 → 医保户口性质值
    "婚姻状态": 8,                  # 默认: 未说明的婚姻状况
    "健康状况": 9,                  # 默认: 健康或良好
    "居住地址": 10,                 # = 地址
    "居住地邮政编码": 11,          # 文本 (前导零), 如 130000.0→130000
    "固定电话": 12,
    "手机号码": 13,                 # = 联系电话 (text, 防科学计数)
    "申报工资": 14,                 # = 合同工资
    "编制类型": 15,                 # 默认: 非在编
    "本次参保时间": 16,             # Excel 序列号; 省医保=合同开始时间, 市医保=医保参保年月+01
}
assert len(MEDICAL_ENROLL_OUTPUT_COLUMNS) == MEDICAL_ENROLL_OUTPUT_COLUMN_COUNT == 17
MEDICAL_ENROLL_OUTPUT_HEADERS = tuple(MEDICAL_ENROLL_OUTPUT_COLUMNS.keys())

# =====================================================================
# OUTPUT 4: 批量减员申报(减员).xls — 医保
# =====================================================================
# Sheet1: R0 = 列名 (3 cols), R1 = 数据起始行.
# Sheet2 = 医保变更原因字典 (57 values; 减员对应「人员中断缴费」类, 如
#   在职人员解除/终止劳动合同). Sheet3 = 空. 兼容性报表 = Excel 兼容性提示.
# 按医保参保属地拆分省/市两个文件; 不追加合同终止原因列 (保持 3 列).
MEDICAL_REDUCE_OUTPUT_FILE = "输入输出/输出/医保/批量减员申报(减员).xls"
MEDICAL_REDUCE_OUTPUT_SHEET = "Sheet1"
MEDICAL_REDUCE_OUTPUT_DICT_SHEET = "Sheet2"  # 医保变更原因 (57 值)
MEDICAL_REDUCE_OUTPUT_HEADER_ROW = 0
MEDICAL_REDUCE_OUTPUT_DATA_START_ROW = 1
MEDICAL_REDUCE_OUTPUT_COLUMN_COUNT = 3

MEDICAL_REDUCE_OUTPUT_COLUMNS = {
    "姓名": 0,
    "证件类型": 1,                  # 字典: 空→居民身份证（户口簿）
    "证件号码": 2,                  # 身份证 (text)
}
assert len(MEDICAL_REDUCE_OUTPUT_COLUMNS) == MEDICAL_REDUCE_OUTPUT_COLUMN_COUNT == 3
MEDICAL_REDUCE_OUTPUT_HEADERS = tuple(MEDICAL_REDUCE_OUTPUT_COLUMNS.keys())
