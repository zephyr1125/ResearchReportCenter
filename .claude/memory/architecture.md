# 架构细节与踩坑记录

## LLM 客户端设计（2026-03-19 重构）

之前 translator/summarizer/highlighter 各自有一份 HTTP 请求逻辑。重构后统一收敛到 `llm_client.py`：

```python
# 所有 LLM 调用统一入口
client = LLMClient(api_key=..., base_url=..., model=...)
response = client.chat(system_prompt, user_content, temperature=0, max_input_chars=20000)
```

创建方式：
- cli.py 中 `_build_llm_client(settings)` 工厂函数，summarizer 和 highlighter 共用同一个配置
- 翻译器有独立的 api_key/base_url/model（LLM_* 前缀），总结+高亮共用 SUMMARY_* 前缀

## PageKind 枚举（2026-03-19 新增）

替代之前散落的字符串 `"content"` / `"appendix"` / `"report_list"`：
- 定义在 `models.py`，类型安全
- `pdf_processor._detect_page_kind()` 返回枚举值
- 判断分支：`cli.py`（翻译跳过、高亮条件）、`site_builder.py`（渲染路由）

## 数值高亮的保护机制

`highlighter.py:apply_numeric_highlights()` 先用正则找到 `<mark class="rrc-highlight-insight">` 区块并保护：
- insight 区块内不再叠加 data 高亮，避免嵌套 `<mark>`
- 处理顺序：先 insight 短语高亮 → 再数值正则高亮

## PDF 页面类型检测

- `appendix`：标题匹配 `disclosures & disclaimer` 等关键词，或 6 个法律关键词命中 ≥3 个
- `report_list`：包含 "Links to recent reports..." 且有 ≥8 条带日期的标题
- `content`：其余所有

## 文本块过滤（pdf_processor）

图表密集页（≥15 个文本块且短文本或数值文本占比过高）会激进过滤：
- 丢弃：页码、纯数值块、图表来源、图片标题、日期轴标签
- 保留：长段落叙述（≥180字符 或 ≥4行且≥120字符）、联系人块

## 高亮函数在 cli.py 中

`apply_page_highlights()` 和 `apply_summary_highlights()` 属于 pipeline 逻辑，目前在 cli.py 中。
如果需要测试高亮编排（短语+数值组合），可将其移到独立模块。

## Volcengine 翻译分块

`_split_text_for_volcengine()` 按换行符优先拆分，单行超长时按字符数硬切（4500 字符限制）。
