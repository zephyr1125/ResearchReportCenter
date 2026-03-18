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

2. 设置环境变量：

```bash
set LLM_API_KEY=your_api_key
set LLM_BASE_URL=https://api.openai.com/v1
set LLM_MODEL=gpt-4.1-mini
```

> `LLM_BASE_URL` 采用 OpenAI 兼容接口，程序会自动请求 `chat/completions`。

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

## 目录说明

- `input/`：原始 PDF 输入目录。
- `output/site_src/docs/`：生成的 Markdown 与资源。
- `output/site/`：最终静态网站。
- `output/logs/`：运行日志。
- `output/state/manifest.json`：增量处理状态。

## GitHub Pages 部署

仓库内已包含 `.github/workflows/deploy-pages.yml`。将生成结果推送到 GitHub 后，可自动构建并部署站点。
