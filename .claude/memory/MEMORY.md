# ResearchReportCenter — 项目记忆

## 一句话概述
金融研报 PDF → 双语 Markdown → MkDocs 静态站。核心命令：`python -m app build-site`。

## 文件地图

```
app/
├── __main__.py      # 入口 → cli.main()
├── cli.py           # CLI 编排：扫描 PDF → 翻译 → 高亮 → 总结 → 渲染 → 写 manifest
├── config.py        # Settings frozen dataclass，从 .env 加载
├── models.py        # 数据模型 + PageKind 枚举
├── llm_client.py    # 共享 OpenAI 兼容 HTTP 客户端（重试、错误处理）
├── translator.py    # Translator ABC → OpenAICompatibleTranslator / VolcengineTranslator
├── summarizer.py    # OpenAICompatibleSummarizer（复用 llm_client）
├── highlighter.py   # OpenAICompatibleHighlighter + 数值/短语高亮正则
├── pdf_processor.py # PyMuPDF 提取文本/图片/页面类型检测
├── site_builder.py  # 渲染 Markdown：报告页、首页索引、报告列表、附录
├── manifest.py      # load/save manifest.json（增量构建状态）
└── utils.py         # sha256_file, slugify, stable_slug, ensure_relative_posix

.claude/
├── settings.json         # 项目级 hooks（PostToolUse → check_structure.sh）
├── settings.local.json   # 个人权限（gitignored）
└── memory/
    ├── MEMORY.md          # 本文件
    └── architecture.md    # 架构细节
scripts/
└── check_structure.sh     # 检测 app/ 结构变化 + 同步记忆文件到全局目录
```

## 关键类型

- `PageKind` 枚举：`CONTENT` / `APPENDIX` / `REPORT_LIST`（替代之前散落的 magic strings）
- `PageKind` 值通过 `pdf_processor._detect_page_kind()` 设置
- `cli.py` 和 `site_builder.py` 用 `PageKind` 做分支判断

## 核心 pipeline（cli.py:run_build_site）

1. 扫描 `input/*.pdf`，计算 SHA-256，对比 manifest 跳过未变文件
2. `PdfProcessor.extract()` → `DocumentContent`（含 pages/items）
3. 遍历 page：翻译 TextBlock → 高亮（AI 短语 + 数值正则）→ 生成 AI 总结
4. `render_report_markdown()` 写入 `output/site_src/docs/reports/{slug}.md`
5. 写 `index.md` / `manifest.json` / `failures.txt`

## LLM 调用架构

所有 OpenAI 兼容调用走 `llm_client.LLMClient.chat()`：
- 翻译：`OpenAICompatibleTranslator(LLMClient)` → `translator.SYSTEM_PROMPT`
- 总结：`OpenAICompatibleSummarizer(LLMClient)` → `summarizer.SUMMARY_SYSTEM_PROMPT`
- 高亮：`OpenAICompatibleHighlighter(LLMClient)` → `highlighter.HIGHLIGHT_SYSTEM_PROMPT`
- 429 自动重试（指数退避，最多 3 次），其他错误立即抛 `LLMError`

## 配置（.env）

```bash
TRANSLATOR_PROVIDER=openai|volcengine
LLM_API_KEY / LLM_BASE_URL / LLM_MODEL       # 翻译用（openai 时）
VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY  # 翻译用（volcengine 时）
SUMMARY_ENABLED=true|false
SUMMARY_API_KEY / SUMMARY_BASE_URL / SUMMARY_MODEL  # 总结+高亮共用
HIGHLIGHT_ENABLED=true|false
```

## 测试

```
tests/
├── test_cli.py            # build_summary_source 排除逻辑
├── test_highlighter.py    # 候选解析 + 数值/短语高亮
├── test_manifest.py       # manifest 读写 round-trip
├── test_pdf_page_kind.py  # 免责声明页检测
├── test_pdf_processor.py  # 文本块过滤逻辑
├── test_site_builder.py   # Markdown 渲染（报告/索引/列表/附录）
├── test_translator.py     # Volcengine 文本分块
└── test_utils.py          # slugify/sha256/stable_slug
```

- 运行：`python -m pytest tests/ -v`
- 纯逻辑测试，不调用真实 API

## 更多细节

详见 [architecture.md](architecture.md)：LLM 客户端设计、PageKind 枚举历史、数值高亮保护机制、PDF 页面类型检测规则、文本块过滤逻辑。

## 常见任务指引

| 我想... | 去这里 |
|---------|--------|
| 改翻译 prompt/system | `translator.py` 顶部 `SYSTEM_PROMPT` |
| 改总结格式 | `summarizer.py` 顶部 `SUMMARY_SYSTEM_PROMPT` |
| 改高亮选词逻辑 | `highlighter.py` 顶部 `HIGHLIGHT_SYSTEM_PROMPT` |
| 改 PDF 噪音过滤 | `pdf_processor.py` `_filter_page_items` / `_should_drop_text_block` |
| 新增页面类型 | `models.py` 加 PageKind 值 + `pdf_processor._detect_page_kind` + `site_builder.render_*` |
| 改首页布局 | `site_builder.py` `render_index_markdown` |
| 加新翻译后端 | 实现 `Translator.translate()` + `cli.build_translator()` |
