# ResearchReportCenter

将放入 `input/` 目录的研报 PDF 增量翻译为双语文章，并生成可部署到 `GitHub Pages` 的静态网站。

## 功能概览

- 扫描 `input/` 目录中的 PDF。
- 通过文件哈希做增量处理，只翻译新增或被修改的文件。
- 保留原始图片与图表，必要时使用页面预览图兜底。
- 生成 `MkDocs` 站点，并输出到 `output/site/`。
- 可通过 GitHub Actions 自动部署到 `GitHub Pages`。

## 环境准备

1. 安装依赖：

```bash
pip install -e .[dev]
```

2. 在项目根目录创建 `.env` 文件。

### 使用 OpenAI

```bash
TRANSLATOR_PROVIDER=openai
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

> 程序会优先读取 `.env`，若 `.env` 缺失，再回退到系统环境变量。  
> `LLM_BASE_URL` 采用 OpenAI 兼容接口，程序会自动请求 `chat/completions`。

### 使用火山引擎机器翻译

```bash
TRANSLATOR_PROVIDER=volcengine
VOLCENGINE_ACCESS_KEY=your_access_key
VOLCENGINE_SECRET_KEY=your_secret_key
VOLCENGINE_REGION=cn-north-1
TARGET_LANGUAGE=zh
```

> 火山引擎使用 `TranslateText` 文本翻译接口，适合当前“文本块翻译 + 原图保留”的实现方式。

## 使用方式

### 增量构建站点

```bash
python -m app build-site
```

### 强制全量重建

```bash
python -m app build-site --force
```

### 仅重建单个文件

```bash
python -m app build-site --file your-report.pdf
```

### 生成预览站点但跳过真实翻译

```bash
python -m app build-site --file your-report.pdf --force --skip-translation
```

## 首个 PDF 的快速验收

目标是尽快完成一次“放入 PDF -> 生成站点 -> 推送 -> 在线查看”的闭环。

1. 将一份真实研报 PDF 放入 `input/` 目录。
2. 配置 `.env`：

```bash
TRANSLATOR_PROVIDER=openai
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

3. 执行构建：

```bash
python -m app build-site --force
mkdocs build --clean
```

如果当前 API 账号没有额度，想先验证站点结构和图片图表效果，可先执行：

```bash
python -m app build-site --file your-report.pdf --force --skip-translation
mkdocs build --clean
```

4. 检查本地产物：

- `output/site_src/docs/reports/` 中应出现对应 Markdown 文章。
- `output/site_src/docs/assets/` 中应出现提取出的图片或页面预览图。
- `output/site/index.html` 应可作为站点首页。

5. 推送到 GitHub 后，确认 Actions 中 `Deploy Pages` 工作流成功。
6. 打开 GitHub Pages 页面，验证首页能看到新研报入口，文章页能看到双语内容和图片图表。

如果首次测试失败，优先检查：

- `output/logs/build-site.log`
- `output/logs/failures.txt`
- `output/state/manifest.json`

如果你使用火山引擎，请改成：

```bash
TRANSLATOR_PROVIDER=volcengine
VOLCENGINE_ACCESS_KEY=your_access_key
VOLCENGINE_SECRET_KEY=your_secret_key
VOLCENGINE_REGION=cn-north-1
TARGET_LANGUAGE=zh
```

## 目录说明

- `input/`：原始 PDF 输入目录。
- `output/site_src/docs/`：生成的 Markdown 与资源。
- `output/site/`：最终静态网站。
- `output/logs/`：运行日志。
- `output/state/manifest.json`：增量处理状态。

## GitHub Pages 部署

仓库内已包含 `.github/workflows/deploy-pages.yml`。将生成结果推送到 GitHub 后，可自动构建并部署站点。
