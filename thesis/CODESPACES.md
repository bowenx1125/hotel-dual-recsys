# 在 GitHub Codespaces 里改论文

1. 打开本仓库，点击 **Code** → **Codespaces** → **Create codespace on main**。
2. 等待环境配置完成。第一次会安装 TeX Live 和 LaTeX Workshop。
3. 打开 `thesis/chapters/` 里要修改的 `.tex` 文件。
4. 保存后会在 `thesis/` 目录用 latexmk（pdfLaTeX）自动编译。按 **Ctrl+Alt+V**（macOS 为 **Cmd+Alt+V**）在编辑器标签页打开 PDF 预览。
5. 在左侧 **Source Control** 里提交并推送。`thesis/main.pdf` 和编译中间文件已由 `thesis/.gitignore` 忽略，不要提交它们。
